import time
import yaml
import botocore
import boto3
import uuid
from datetime import datetime
from clint.textui import columns, colored, puts
from .manifest import Manifest


DESCRIBE_ATTEMPTS = 120
DESCRIBE_WAIT = 5
STATUS_NO_CHANGE = "The submitted information didn't contain changes. "\
                   "Submit different information to create a change set."

STACK_STATUS_COLOR = {
    'CREATE_COMPLETE': colored.green,
    'DELETE_COMPLETE': colored.green,
    'DELETE_SKIPPED': colored.green,
    'UPDATE_COMPLETE': colored.green,
    'CREATE_FAILED': colored.red,
    'DELETE_FAILED': colored.red,
    'UPDATE_FAILED': colored.red,
    'CREATE_IN_PROGRESS': colored.yellow,
    'DELETE_IN_PROGRESS': colored.yellow,
    'UPDATE_IN_PROGRESS': colored.yellow,
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS': colored.yellow,
    }

STACK_STATUS_END = [
    'CREATE_COMPLETE',
    'DELETE_COMPLETE',
    'UPDATE_COMPLETE',
    'CREATE_FAILED',
    'UPDATE_FAILED',
    'DELETE_FAILED',
]
STACK_CHANGE_COLOR = {
    'ADD': colored.green,
    'MODIFY': colored.yellow,
    'REPLACE': colored.red,
    'REMOVE': colored.red,
}



def _display_stack_events(client, stack_arn, request_token=None):
    processed = set()
    for attempt in range(DESCRIBE_ATTEMPTS):
        response = client.describe_stack_events(
            StackName=stack_arn,
        )
        events = response['StackEvents']
        if request_token is not None:
            events = [
                event for event in events
                if event.get('ClientRequestToken') == request_token
            ]
        events.sort(key=lambda x: x['Timestamp'])
        for event in events:
            event_id = event['EventId']
            resource = event['LogicalResourceId']
            status = event['ResourceStatus']

            if event_id in processed:
                continue
            else:
                processed.add(event_id)

            color = STACK_STATUS_COLOR.get(status, colored.white)
            puts(columns([color(status), 35], [resource, 40]))
            if event['PhysicalResourceId'] == stack_arn and status in STACK_STATUS_END:
                return status
        time.sleep(DESCRIBE_WAIT)


def _display_stack_changes(changes):
    for change in changes:
        change = change['ResourceChange']
        resource = change['LogicalResourceId']
        if change['Action'] == 'Modify' and change['Replacement'] == 'True':
            action = 'REPLACE'
        else:
            action = change['Action'].upper()
        color = STACK_CHANGE_COLOR[action]
        puts(columns([color(action), 35], [resource, 40]))


def timestamp():
    return int(time.time()*1000)


CFN_IAM_POLICY = """{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:*",
                "cloudformation:CreateStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:DescribeStackResources",
                "cloudformation:GetTemplate",
                "cloudformation:ValidateTemplate"
            ],
            "Resource": "*"
        }
    ]
}"""

        
class CfnSession(object):
    def __init__(self, assume_role_arn=None, parameters_file=None,
                 tags_file=None, manifest_file=None):
        self.assume_role_arn = assume_role_arn
        self.parameters_file = parameters_file or 'parameters.yml'
        self.tags_file = tags_file or 'tags.yml'
        self.manifest = Manifest(manifest_file or 'cfn-manifest.json')

    @property
    def client(self):
        if hasattr(self, '_cfn_client'):
            return self._cfn_client

        if self.assume_role_arn:
            sts = boto3.client('sts')
            response = sts.assume_role(
                DurationSeconds=900,
                #Policy=CFN_IAM_POLICY,
                RoleArn=self.assume_role_arn,
                RoleSessionName='cfn-ci-{}'.format(timestamp())
            )
            
            credentials = response['Credentials']
            self._cfn_client = boto3.client(
                'cloudformation',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
            )
        else:
            self._cfn_client = boto3.client('cloudformation')

        return self._cfn_client

    @property
    def parameters(self):
        try:
            with open(self.parameters_file, 'r') as fd:
                parameters = yaml.load(fd)
        except IOError:
            return []
        return [
            {
                'ParameterKey': key,
                'ParameterValue': value,
            }
            for key, value in parameters.items()
        ]

    @property
    def tags(self):
        try:
            with open(self.tags_file, 'r') as fd:
                tags = yaml.load(fd)
        except IOError:
            return []
        return [
            {
                'TagKey': key,
                'TagValue': value,
            }
            for key, value in tags.items()
        ]

    def _stack_exists(self, stack_name_or_arn):
        response = self.client.list_stacks()
        while True:
            for stack in response['StackSummaries']:
                if stack['StackStatus'] == 'DELETE_COMPLETE':
                    continue
                if stack['StackId'] == stack_name_or_arn:
                    return True
                if stack['StackName'] == stack_name_or_arn:
                    return True
            next_token = response.get('NextToken', None)
            if next_token:
                response = self.client.list_stacks(NextToken=next_token)
            else:
                return False

    def create_change_set(self, stack_name, template):
        status = 'UNKNOWN'
        change_set_name = 'cfn-ci-{}'.format(timestamp())
        description = 'Autogenerated by cfn-ci.'

        kwargs = {
            'StackName': stack_name,
            'ChangeSetName': change_set_name,
            'Description': description,
            'TemplateBody': template,
            'Parameters': self.parameters,
            #'Tags': self.tags,
        }

        if not self._stack_exists(stack_name):
            kwargs['ChangeSetType'] = 'CREATE'

        #import pprint; pprint.pprint(kwargs)
        response = self.client.create_change_set(**kwargs)
        stack_arn = response['StackId']
        change_set_arn = response['Id']
        self.manifest.stack_arn = stack_arn
        self.manifest.change_set_arn = change_set_arn

        for attempt in range(DESCRIBE_ATTEMPTS):
            response = self.client.describe_change_set(
                ChangeSetName=change_set_arn,
            )
            status = response['Status']
            changes = response['Changes']
            if status == 'FAILED' and response['StatusReason'] == STATUS_NO_CHANGE:
                self.client.delete_change_set(
                    ChangeSetName=change_set_arn
                )
                status = 'NO_CHANGE'
                break
            elif status not in ['CREATE_IN_PROGRESS', 'CREATE_PENDING']:
                break
            time.sleep(DESCRIBE_WAIT)
        _display_stack_changes(changes)
        return change_set_arn

    def show_change_set(self, change_set_arn=None):
        if change_set_arn is None:
            change_set_arn = self.manifest.change_set_arn
        response = self.client.describe_change_set(
            ChangeSetName=change_set_arn,
        )
        if response['Status'] not in ['AVAILABLE', 'CREATE_COMPLETE']:
            print(response['Status'])
        else:
            _display_stack_changes(response['Changes'])

    def apply_change_set(self, change_set_arn=None):
        if change_set_arn is None:
            change_set_arn = self.manifest.change_set_arn
        response = self.client.describe_change_set(
            ChangeSetName=change_set_arn,
        )

        request_token = str(uuid.uuid4())
        stack_arn = response['StackId']
        self.client.execute_change_set(
            ChangeSetName=change_set_arn,
            ClientRequestToken=request_token,
        )
        status = _display_stack_events(self.client, stack_arn, request_token)
        if status == 'SUCCESS':
            del self.manifest.change_set_arn
        return status

    def delete_stack(self, stack_arn=None):
        if stack_arn is None:
            stack_arn = self.manifest.stack_arn
        request_token = str(uuid.uuid4())
        self.client.delete_stack(
            StackName=stack_arn,
            ClientRequestToken=request_token,
        )
        status = _display_stack_events(self.client, stack_arn, request_token)
        if status == 'DELETE_COMPLETE':
            del self.manifest.stack_arn
        return status

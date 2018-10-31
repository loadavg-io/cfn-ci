import sys
import click
import importlib
from .manifest import Manifest
from .tools import CfnSession


@click.group()
def cli():
    pass


@cli.command('create-change-set')
@click.argument('stack-name')
@click.argument('template', type=click.File('r'))
@click.option('--assume-role-arn', default=None)
def cli_create_change_set(stack_name, template, assume_role_arn=None):
    session = CfnSession(assume_role_arn)
    change_set_arn = session.create_change_set(stack_name, template.read())
    click.echo(change_set_arn)


@cli.command('show-change-set')
@click.argument('change-set-arn', required=False)
@click.option('--assume-role-arn', default=None)
def cli_show_change_set(change_set_arn, assume_role_arn=None):
    session = CfnSession(assume_role_arn)
    session.show_change_set(change_set_arn)


@cli.command('apply-change-set')
@click.argument('change-set-arn', required=False)
@click.option('--assume-role-arn', default=None)
def cli_apply_change_set(stack_name=None, change_set_arn=None, assume_role_arn=None):
    session = CfnSession(assume_role_arn)
    status = session.apply_change_set(change_set_arn)
    if status != 'SUCCESS':
        click.echo(status)


@cli.command('delete-stack')
@click.argument('stack-arn', required=False)
@click.option('--assume-role-arn', default=None)
@click.confirmation_option()
def cli_destroy_stack(stack_arn=None, assume_role_arn=None):
    session = CfnSession(assume_role_arn)
    session.delete_stack(stack_arn)

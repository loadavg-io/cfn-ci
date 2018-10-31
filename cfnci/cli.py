import sys
import click
import importlib
from .manifest import Manifest
from .tools import (
    exists, create, update, destroy,
    create_change_set, show_change_set, apply_change_set
)


@click.group()
def cli():
    pass


@cli.command('update-stack')
@click.argument('stack-name')
@click.argument('template', type=click.File('r'))
def cli_update_stack(stack_name, template):
    if not exists(stack_name):
        stack_arn = create(stack_name, template.read())
    else:
        stack_arn = update(stack_name, template.read())
    manifest = Manifest()
    manifest.stack_arn = stack_arn
    manifest.save()
    click.echo(stack_arn)


@cli.command('create-change-set')
@click.argument('stack-name')
@click.argument('template', type=click.File('r'))
def cli_create_change_set(stack_name, template):
    change_set_arn = create_change_set(stack_name, template.read())
    manifest = Manifest()
    manifest.change_set_arn = change_set_arn
    manifest.save()
    click.echo(change_set_arn)


@cli.command('show-change-set')
@click.argument('change-set-arn', required=False)
def cli_show_change_set(change_set_arn):
    manifest = Manifest()
    show_change_set(manifest.change_set_arn)


@cli.command('apply-change-set')
@click.argument('stack-name', required=False)
@click.argument('change-set-name', required=False)
def cli_apply_change_set(stack_name=None, change_set_name=None):
    manifest = Manifest()
    status = apply_change_set(None, manifest.change_set_arn)
    if status == 'SUCCESS':
        del manifest.manifest['change_set_arn']
        manifest.save()
    else:
        click.echo(status)


@cli.command('destroy-stack')
@click.argument('stack-name', required=False)
@click.confirmation_option()
def cli_destroy_stack(stack_name=None):
    manifest = Manifest()
    stack_name = stack_name or manifest.stack_arn
    if not exists(stack_name):
        click.echo('Stack with name "%s" does not exist.' % stack_name)
        sys.exit(1)
    else:
        destroy(stack_name)

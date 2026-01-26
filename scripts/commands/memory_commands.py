# commands/memory_commands.py
import json
from datetime import datetime

import click


@click.group()
def memory():
    """Memory management commands."""
    pass

@memory.command()
@click.pass_context
def status(ctx):
    """Show memory status and statistics."""
    memory_monitor = ctx.obj['memory_monitor']
    report = memory_monitor.get_memory_report()
    click.echo(report)
    
    # Save detailed report to file
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"memory_report_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(memory_monitor.stats, f, indent=2)
    click.echo(f"\nDetailed report saved to {filename}")

@memory.command()
@click.argument('token_address')
@click.pass_context
def inspect(ctx, token_address):
    """Inspect a specific token in memory."""
    memory = ctx.obj['memory']
    token = memory.get_token(token_address.lower())
    
    if not token:
        click.echo(f"Token {token_address} not found in memory")
        return
        
    click.echo(json.dumps(token, indent=2, default=str))

import typer
from rich.console import Console

app = typer.Typer(
    name="factory",
    help="Narrative Factory CLI - AI-powered storytelling engine",
    no_args_is_help=True
)

console = Console()

@app.command()
def generate(seed: str = typer.Argument(..., help="Chapter seed text")):
    console.print(f"Starting generation with seed: {seed}")
    console.print("Implementation pending - placeholder command")

@app.command()
def status():
    console.print("No jobs pending review")
    console.print("Implementation pending - placeholder command")

@app.command()
def test():
    console.print("Narrative Factory CLI is working\!")
    console.print("MVP scaffolding complete")

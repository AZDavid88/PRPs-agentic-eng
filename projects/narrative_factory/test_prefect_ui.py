#!/usr/bin/env python3
"""Test script to verify Prefect UI connection and create a simple flow."""

import asyncio
from datetime import datetime

from prefect import flow, task


@task
def simple_task(name: str) -> str:
    """A simple task for testing."""
    return f"Hello from {name} at {datetime.now()}"


@flow(name="Test Flow for Prefect UI")
def simple_flow() -> str:
    """A simple flow to test Prefect UI connection."""
    result = simple_task("narrative_factory")
    return result


if __name__ == "__main__":
    print("🚀 Testing Prefect UI Connection")
    print("=" * 50)
    
    # Run the simple flow
    result = simple_flow()
    print(f"Flow result: {result}")
    
    print("\n✅ Flow execution complete!")
    print("Check the Prefect UI at: http://127.0.0.1:4200/")
    print("You should see the 'Test Flow for Prefect UI' run")
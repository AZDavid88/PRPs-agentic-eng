#!/usr/bin/env python3
"""
Demonstration of Phase 3 Continuity Engine
Shows how story state persists across chapters
"""

import asyncio
from src.services.state_manager import StateManager
from src.models.story_state import StoryState

async def demonstrate_continuity():
    print("=== NARRATIVE FACTORY CONTINUITY ENGINE DEMO ===\n")
    
    # Initialize StateManager
    sm = StateManager()
    
    # === CHAPTER 1: Story Beginning ===
    print("📖 CHAPTER 1: The Mysterious Arrival")
    print("-" * 40)
    
    # Create initial story state
    story_state = StoryState(current_chapter=1)
    story_state.narrative_tone = "mysterious"
    story_state.pacing_state = "moderate"
    
    # Add initial plot threads
    thread1 = story_state.add_plot_thread(
        "Stranger arrives during thunderstorm", 
        priority=9, 
        characters=["Protagonist", "Stranger"]
    )
    
    thread2 = story_state.add_plot_thread(
        "Ancient artifact goes missing from museum",
        priority=7,
        characters=["Protagonist", "Museum Curator"]
    )
    
    # Add protagonist's initial knowledge
    story_state.add_knowledge_revelation(
        "The stranger carries an ornate medallion",
        "confirmed",
        ["Medallion might be connected to missing artifact"]
    )
    
    # Add some tensions
    story_state.unresolved_tensions.extend([
        "Who is the stranger and why did they come here?",
        "What happened to the museum's prized artifact?",
        "Why did the stranger arrive during the storm?"
    ])
    
    print(f"✅ Plot threads: {len(story_state.active_plot_threads)}")
    print(f"✅ Knowledge items: {len(story_state.protagonist_knowledge)}")
    print(f"✅ Unresolved tensions: {len(story_state.unresolved_tensions)}")
    
    # Save Chapter 1 state
    await sm.save_state(story_state)
    print(f"💾 Chapter 1 state saved\n")
    
    # === CHAPTER 2: Investigation Begins ===
    print("📖 CHAPTER 2: Secrets Revealed")
    print("-" * 40)
    
    # Simulate Canonist output for Chapter 2
    canonist_report = {
        "NEW_TENSION_STATE_REPORT": [
            "Museum curator is acting suspiciously",
            "Medallion glows when near the empty display case",
            "Stranger refuses to answer direct questions"
        ],
        "NEW_KNOWLEDGE_STATE": [
            "The medallion is a key to an ancient vault",
            "The curator has been stealing artifacts for years",
            "The stranger is actually a guardian sent to retrieve the artifacts"
        ]
    }
    
    # Update story state based on canonist analysis
    updated_state = sm.create_state_from_canonist_output(canonist_report, story_state)
    
    # Resolve one plot thread
    updated_state.resolve_plot_thread(thread2)
    
    print(f"✅ New chapter: {updated_state.current_chapter}")
    print(f"✅ New tensions: {len(updated_state.unresolved_tensions)}")
    print(f"✅ New knowledge: {len(updated_state.protagonist_knowledge)}")
    print(f"✅ Resolved threads: {len([t for t in updated_state.active_plot_threads if t.status == 'resolved'])}")
    
    # Save Chapter 2 state
    await sm.save_state(updated_state)
    print(f"💾 Chapter 2 state saved\n")
    
    # === CHAPTER 3: Confrontation ===
    print("📖 CHAPTER 3: The Truth Emerges")
    print("-" * 40)
    
    # Simulate another chapter
    canonist_report_3 = {
        "NEW_TENSION_STATE_REPORT": [
            "Final confrontation with the corrupt curator",
            "The vault beneath the museum is opened",
            "More guardians arrive to help"
        ],
        "NEW_KNOWLEDGE_STATE": [
            "The artifacts were meant to be protected, not displayed",
            "The protagonist has been chosen as the new guardian",
            "The storm was a magical summons"
        ]
    }
    
    final_state = sm.create_state_from_canonist_output(canonist_report_3, updated_state)
    
    # Resolve the main plot thread
    final_state.resolve_plot_thread(thread1)
    
    print(f"✅ Final chapter: {final_state.current_chapter}")
    print(f"✅ Total knowledge gained: {len(final_state.protagonist_knowledge)}")
    print(f"✅ All plot threads resolved: {all(t.status == 'resolved' for t in final_state.active_plot_threads)}")
    
    await sm.save_state(final_state)
    print(f"💾 Chapter 3 state saved\n")
    
    # === DEMONSTRATE CONTINUITY ===
    print("🔄 CONTINUITY DEMONSTRATION")
    print("-" * 40)
    
    # Load the story state and show continuity
    loaded_state = await sm.load_latest_state()
    
    print("📊 STORY PROGRESSION SUMMARY:")
    print(f"   📖 Chapters completed: {loaded_state.current_chapter}")
    print(f"   🧵 Plot threads: {len(loaded_state.active_plot_threads)}")
    print(f"   🧠 Knowledge items: {len(loaded_state.protagonist_knowledge)}")
    print(f"   ⚡ Unresolved tensions: {len(loaded_state.unresolved_tensions)}")
    
    print("\n🧠 PROTAGONIST'S KNOWLEDGE JOURNEY:")
    for i, knowledge in enumerate(loaded_state.protagonist_knowledge, 1):
        print(f"   {i}. Chapter {knowledge.chapter_discovered}: {knowledge.concept}")
        print(f"      Status: {knowledge.confirmation_level}")
        if knowledge.implications:
            print(f"      Implications: {', '.join(knowledge.implications)}")
    
    print("\n🧵 PLOT THREAD RESOLUTION:")
    for thread in loaded_state.active_plot_threads:
        status_emoji = "✅" if thread.status == "resolved" else "🔄"
        print(f"   {status_emoji} {thread.description}")
        print(f"      Priority: {thread.priority}/10, Status: {thread.status}")
        print(f"      Chapters: {thread.introduced_chapter} → {thread.last_updated_chapter}")
    
    # Show state summary for next chapter
    summary = await sm.get_state_summary()
    print(f"\n📋 READY FOR NEXT CHAPTER:")
    print(f"   Current chapter: {summary['current_chapter']}")
    print(f"   Active plot threads: {summary['active_plot_threads']}")
    print(f"   Knowledge base: {summary['knowledge_revelations']} items")
    print(f"   Narrative tone: {summary['narrative_tone']}")
    print(f"   Pacing: {summary['pacing_state']}")
    
    print("\n🎯 CONTINUITY BENEFITS:")
    print("   ✅ No plot threads forgotten")
    print("   ✅ Character knowledge tracked")
    print("   ✅ Tension escalation managed")
    print("   ✅ Story consistency maintained")
    print("   ✅ AI has full context for next chapter")

if __name__ == "__main__":
    asyncio.run(demonstrate_continuity())
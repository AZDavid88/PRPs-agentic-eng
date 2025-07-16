"""
Unit tests for agent personas and Pydantic model validation.
Tests based on PRP_MVP_02_AGENT_CORE.md requirements.
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add the src directory to the path so we can import from narrative_factory
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from agents.models import ChapterBeatStructure, ChapterBlueprint, ChapterMetadata, StrategicBrief
from agents.personas import CanonistAgent, DirectorAgent, TacticianAgent, WeaverAgent


class TestDirectorAgent:
    """Test the DirectorAgent class and its Pydantic model outputs."""

    @patch('agents.personas.GENAI_AVAILABLE', True)
    @patch('agents.personas.genai')
    def test_director_agent_initialization(self, mock_genai):
        """Test that DirectorAgent initializes correctly."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            mock_client = Mock()
            mock_genai.Client.return_value = mock_client

            agent = DirectorAgent()
            assert agent.persona_name == "director"
            assert agent.client_type == "gemini"
            assert agent.client == mock_client

    def test_director_agent_execution_mocked(self, mocker):
        """Tests the execute method with a mocked LLM call to ensure it returns a valid Pydantic model."""
        # Mock the LLM client's response
        mock_response = mocker.MagicMock()

        # The mock must return a JSON string that matches the StrategicBrief schema
        mock_brief_dict = {
            "title": "Test Chapter Title",
            "scope": "SINGLE_CHAPTER",
            "estimated_chapters": "1",
            "pov_character_id": "char_protagonist",
            "goal": "Test narrative goal",
            "key_events": ["Event 1", "Event 2"],
            "emotional_turning_point": "Character realizes truth",
            "cliffhanger_concept": "Mysterious figure appears"
        }
        mock_response.text = json.dumps(mock_brief_dict)

        # Mock the environment and client
        with patch('agents.personas.GENAI_AVAILABLE', True):
            with patch('agents.personas.genai') as mock_genai:
                with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
                    mock_client = Mock()
                    mock_client.models.generate_content.return_value = mock_response
                    mock_genai.Client.return_value = mock_client

                # Create agent and execute
                agent = DirectorAgent()
                result = agent.execute("Test chapter seed.")

                # Assert that the output is a valid Pydantic model
                assert isinstance(result, StrategicBrief)
                assert result.title == "Test Chapter Title"
                assert result.scope == "SINGLE_CHAPTER"
                assert result.pov_character_id == "char_protagonist"
                assert len(result.key_events) == 2
                assert result.key_events[0] == "Event 1"

    def test_director_agent_execution_with_openai(self, mocker):
        """Test DirectorAgent with OpenAI client."""
        mock_response = {
            "title": "OpenAI Test Chapter",
            "scope": "MULTI_CHAPTER_ARC",
            "estimated_chapters": "2-3",
            "pov_character_id": "char_mentor",
            "goal": "Advance the protagonist's journey",
            "key_events": ["Discovery", "Conflict", "Resolution"],
            "emotional_turning_point": "Trust is broken",
            "cliffhanger_concept": "Betrayal revealed"
        }

        mock_chat_response = Mock()
        mock_chat_response.choices = [Mock()]
        mock_chat_response.choices[0].message.content = json.dumps(mock_response)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_chat_response

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            with patch('agents.personas.OpenAI', return_value=mock_client):
                agent = DirectorAgent(client_type="openai")
                result = agent.execute("Test seed for OpenAI")

                assert isinstance(result, StrategicBrief)
                assert result.title == "OpenAI Test Chapter"
                assert result.scope == "MULTI_CHAPTER_ARC"
                assert len(result.key_events) == 3


class TestTacticianAgent:
    """Test the TacticianAgent class and its Pydantic model outputs."""

    def test_tactician_agent_execution_mocked(self, mocker):
        """Tests the Tactician execute method with mocked input and output."""
        # Create a valid StrategicBrief as input
        input_brief = StrategicBrief(
            title="Input Chapter",
            scope="SINGLE_CHAPTER",
            estimated_chapters="1",
            pov_character_id="char_protagonist",
            goal="Test strategic goal",
            key_events=["Strategic event"],
            emotional_turning_point="Character growth",
            cliffhanger_concept="Mystery deepens"
        )

        # Mock response for ChapterBlueprint
        mock_blueprint_dict = {
            "metadata": {
                "chapter_goal": "Execute the strategic vision",
                "hook_concept": "Cliffhanger that compels reading",
                "discovery_log": ["Character learns truth", "New ally revealed"]
            },
            "title_suggestions": ["Chapter Title A", "Chapter Title B", "Chapter Title C"],
            "beats": [
                {
                    "moment_anchor": "Character stands at the threshold",
                    "internal_shift": "Doubt transforms to resolve",
                    "micro_conflict": "Door is locked",
                    "narrative_payoff": "Key is found in unexpected place",
                    "pacing_density": "Moderate"
                },
                {
                    "moment_anchor": "Footsteps echo in the hallway",
                    "internal_shift": "Fear becomes curiosity",
                    "micro_conflict": "Shadow moves ahead",
                    "narrative_payoff": "Identity of follower revealed",
                    "pacing_density": "Crescendo"
                }
            ],
            "brief_id": "brief_input_chapter"
        }

        mock_response = Mock()
        mock_response.text = json.dumps(mock_blueprint_dict)

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            with patch('agents.personas.genai') as mock_genai:
                mock_client = Mock()
                mock_client.models.generate_content.return_value = mock_response
                mock_genai.Client.return_value = mock_client

                agent = TacticianAgent()
                result = agent.execute(input_brief)

                # Assert that the output is a valid ChapterBlueprint Pydantic model
                assert isinstance(result, ChapterBlueprint)
                assert isinstance(result.metadata, ChapterMetadata)
                assert result.metadata.chapter_goal == "Execute the strategic vision"
                assert len(result.title_suggestions) == 3
                assert len(result.beats) == 2
                assert isinstance(result.beats[0], ChapterBeatStructure)
                assert result.beats[0].moment_anchor == "Character stands at the threshold"
                assert result.beats[1].pacing_density == "Crescendo"
                assert result.brief_id == "brief_input_chapter"


class TestWeaverAgent:
    """Test the WeaverAgent placeholder implementation."""

    def test_weaver_agent_initialization(self):
        """Test that WeaverAgent initializes correctly."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            with patch('agents.personas.genai'):
                agent = WeaverAgent()
                assert agent.persona_name == "weaver"

    def test_weaver_agent_execution_placeholder(self):
        """Test the placeholder execute method."""
        mock_blueprint = Mock()
        mock_blueprint.metadata.chapter_goal = "Test goal"

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            with patch('agents.personas.genai'):
                agent = WeaverAgent()
                result = agent.execute(mock_blueprint)

                assert isinstance(result, str)
                assert "Test goal" in result


class TestCanonistAgent:
    """Test the CanonistAgent placeholder implementation."""

    def test_canonist_agent_initialization(self):
        """Test that CanonistAgent initializes correctly."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            with patch('agents.personas.genai'):
                agent = CanonistAgent()
                assert agent.persona_name == "canonist"

    def test_canonist_agent_execution_placeholder(self):
        """Test the placeholder execute method."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            with patch('agents.personas.genai'):
                agent = CanonistAgent()
                result = agent.execute("Test content")

                assert isinstance(result, dict)
                assert "validation_status" in result
                assert result["validation_status"] == "passed"


class TestPydanticModelValidation:
    """Test Pydantic model validation directly."""

    def test_strategic_brief_validation(self):
        """Test that StrategicBrief validates correctly."""
        valid_data = {
            "title": "Test Chapter",
            "scope": "SINGLE_CHAPTER",
            "estimated_chapters": "1",
            "pov_character_id": "char_test",
            "goal": "Test objective",
            "key_events": ["Event 1"],
            "emotional_turning_point": "Character growth",
            "cliffhanger_concept": "Mystery revealed"
        }

        brief = StrategicBrief.model_validate(valid_data)
        assert brief.title == "Test Chapter"
        assert brief.scope == "SINGLE_CHAPTER"

    def test_strategic_brief_validation_error(self):
        """Test that StrategicBrief raises validation errors for invalid data."""
        invalid_data = {
            "title": "Test Chapter",
            "scope": "INVALID_SCOPE",  # Invalid literal
            "estimated_chapters": "1",
            "pov_character_id": "char_test",
            "goal": "Test objective",
            "key_events": ["Event 1"],
            "emotional_turning_point": "Character growth",
            "cliffhanger_concept": "Mystery revealed"
        }

        with pytest.raises(ValueError):
            StrategicBrief.model_validate(invalid_data)

    def test_chapter_blueprint_validation(self):
        """Test that ChapterBlueprint validates correctly."""
        valid_data = {
            "metadata": {
                "chapter_goal": "Test goal",
                "hook_concept": "Test hook",
                "discovery_log": ["Discovery 1"]
            },
            "title_suggestions": ["Title 1", "Title 2"],
            "beats": [
                {
                    "moment_anchor": "Test anchor",
                    "internal_shift": "Test shift",
                    "micro_conflict": "Test conflict",
                    "narrative_payoff": "Test payoff",
                    "pacing_density": "Moderate"
                }
            ],
            "brief_id": "test_brief"
        }

        blueprint = ChapterBlueprint.model_validate(valid_data)
        assert blueprint.metadata.chapter_goal == "Test goal"
        assert len(blueprint.beats) == 1
        assert blueprint.beats[0].pacing_density == "Moderate"

import pytest
import pandas as pd
from agents import ResponseProcessor, DataAnalysisAgent


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'age': [25, 30, 35],
        'score': [88, 92, 85],
    })


@pytest.fixture
def agent_for_extraction():
    """Create a DataAnalysisAgent instance for testing error extraction.
    df and response_processor are None since _extract_response_from_error
    doesn't depend on them."""
    # We only need the agent for its _extract_response_from_error method
    agent = DataAnalysisAgent.__new__(DataAnalysisAgent)
    return agent


class TestExtractResponseFromError:
    """Tests for DataAnalysisAgent._extract_response_from_error — the middle layer of fault tolerance."""

    def test_extract_backtick_content(self, agent_for_extraction):
        """Strategy 1: find longest content between backticks."""
        error_msg = (
            "Could not parse LLM output: `The dataset contains 891 rows and 15 columns. "
            "The age column has 177 missing values. The survival rate is 38.4%. "
            "Further analysis shows strong correlation between pclass and survival.`"
        )
        result = agent_for_extraction._extract_response_from_error(error_msg)
        assert result is not None
        assert "891 rows" in result
        assert "15 columns" in result

    def test_extract_parse_error_content(self, agent_for_extraction):
        """Strategy 2: extract after 'Could not parse LLM output:'."""
        error_msg = (
            "Could not parse LLM output: The dataset has 891 rows and 15 columns. "
            "There are missing values in age, deck, and embarked columns.\n\n"
            "Some additional error context..."
        )
        result = agent_for_extraction._extract_response_from_error(error_msg)
        assert result is not None
        assert "891 rows" in result
        assert "missing values" in result

    def test_extract_content_lines(self, agent_for_extraction):
        """Strategy 3: extract content lines that look like analysis."""
        error_msg = """An error occurred during parsing.
The analysis shows the data has interesting patterns.
Our findings indicate a strong trend in the results.
Error: could not parse the output.
Traceback (most recent call last):
  File "...", line ...
Exception: something went wrong"""
        result = agent_for_extraction._extract_response_from_error(error_msg)
        assert result is not None
        assert "interesting patterns" in result
        assert "strong trend" in result
        # Error/traceback lines should be excluded
        assert "Traceback" not in result
        assert "could not parse" not in result

    def test_no_extractable_content_returns_none(self, agent_for_extraction):
        """Random error with no usable content should return None."""
        error_msg = "Something went completely wrong. Error code: 500. Please try again."
        result = agent_for_extraction._extract_response_from_error(error_msg)
        assert result is None

    def test_short_backtick_ignored(self, agent_for_extraction):
        """Backtick content shorter than 50 chars should not be matched by Strategy 1."""
        # This error_msg does NOT start with "Could not parse LLM output:",
        # so Strategy 2 won't trigger either. Only Strategy 3 (content lines)
        # could match, but there are no analysis-related keywords here.
        error_msg = "An output parsing error occurred: `short` and nothing else useful here."
        result = agent_for_extraction._extract_response_from_error(error_msg)
        assert result is None


class TestResponseProcessor:
    """Tests for ResponseProcessor.process_response."""

    def test_no_code_in_response_returns_unchanged(self, sample_df):
        """Response without any Python code should be returned as-is."""
        rp = ResponseProcessor(sample_df)
        response = "The dataset has 3 rows and 3 columns. Everything looks good."
        result = rp.process_response(response)
        assert result == response

    def test_skips_second_execution(self, sample_df):
        """After one visualization is executed, second call should skip."""
        rp = ResponseProcessor(sample_df)
        # Manually set flag as if a visualization was just executed
        rp.visualization_executed = True
        response = "```python\nax.plot(df['age'], df['score'], 'o')\n```"
        result = rp.process_response(response)
        # Should reset flag and return unchanged
        assert result == response
        assert rp.visualization_executed is False

    def test_extracts_and_cleans_code(self, sample_df):
        """Response with code block should be cleaned of code markers."""
        rp = ResponseProcessor(sample_df)
        response = """## Analysis

Here is the age distribution:

```python
import matplotlib.pyplot as plt
ax.plot(df['age'], df['score'], 'o')
ax.set_xlabel('Age')
ax.set_ylabel('Score')
```

The plot shows a positive correlation between age and score."""
        result = rp.process_response(response)
        # Code block should be removed
        assert "```python" not in result
        assert "ax.plot" not in result
        # Text content preserved
        assert "positive correlation" in result

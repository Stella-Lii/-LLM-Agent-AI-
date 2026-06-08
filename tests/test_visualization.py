import pytest
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend for headless testing

from visualization import VisualizationHandler


@pytest.fixture
def sample_df():
    """Small test dataframe."""
    return pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'age': [25, 30, 35, 28],
        'score': [88, 92, 85, 95],
    })


class TestGetExecutionContext:
    """Tests for VisualizationHandler.get_execution_context."""

    def test_without_df(self):
        ctx = VisualizationHandler.get_execution_context()
        assert 'plt' in ctx
        assert 'np' in ctx
        assert 'pd' in ctx
        assert 'sns' in ctx
        assert 'df' not in ctx

    def test_with_df(self, sample_df):
        ctx = VisualizationHandler.get_execution_context(sample_df)
        assert 'df' in ctx
        assert ctx['df'] is sample_df
        assert 'plt' in ctx
        assert 'pd' in ctx


class TestExecuteVisualizationCode:
    """Tests for VisualizationHandler.execute_visualization_code."""

    def test_valid_code_returns_success(self, sample_df):
        code = """
import matplotlib.pyplot as plt
ax.plot(df['age'], df['score'], 'o')
ax.set_xlabel('Age')
ax.set_ylabel('Score')
"""
        success, message = VisualizationHandler.execute_visualization_code(
            code, df=sample_df, display=False
        )
        assert success is True
        assert "successfully" in message.lower()

    def test_code_with_plt_show_is_sanitized(self, sample_df):
        code = """
import matplotlib.pyplot as plt
ax.plot(df['age'], df['score'], 'o')
plt.show()
"""
        success, message = VisualizationHandler.execute_visualization_code(
            code, df=sample_df, display=False
        )
        assert success is True

    def test_invalid_code_returns_failure(self, sample_df):
        code = "ax.plot(nonexistent_variable)"
        success, message = VisualizationHandler.execute_visualization_code(
            code, df=sample_df, display=False
        )
        assert success is False
        assert "Error" in message

    def test_code_uses_numpy(self, sample_df):
        code = """
import numpy as np
x = np.array([1, 2, 3, 4])
ax.plot(x, df['score'], 's-')
"""
        success, message = VisualizationHandler.execute_visualization_code(
            code, df=sample_df, display=False
        )
        assert success is True

    def test_code_uses_seaborn(self, sample_df):
        code = """
import seaborn as sns
sns.barplot(data=df, x='name', y='score', ax=ax)
"""
        success, message = VisualizationHandler.execute_visualization_code(
            code, df=sample_df, display=False
        )
        assert success is True

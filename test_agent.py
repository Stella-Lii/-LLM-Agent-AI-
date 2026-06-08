"""
Integration tests for the DataAnalysisAgent using the Titanic dataset.

These tests make REAL LLM API calls to DeepSeek and cost money.
Run separately from the fast unit tests:

    pytest test_agent.py -v          # all integration tests
    pytest test_agent.py -v -k "fact"  # only fact-checking tests
    pytest test_agent.py -v -k "viz"   # only visualization tests

The unit tests (tests/) do NOT trigger these - they run offline with no API key.
"""
import matplotlib
matplotlib.use('Agg')  # MUST be before any project imports

import pytest
import os
import re
import pandas as pd
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv()

from agents import DataAnalysisAgent, ResponseProcessor


# ── Ground Truth ──────────────────────────────────────────────────────────

csv_path = "./titanic.csv"  # 将 titanic.csv 放在项目根目录下
df_true = pd.read_csv(csv_path)

GROUND_TRUTH = {
    "rows": 891,
    "cols": 15,
    "age_missing": int(df_true['age'].isna().sum()),       # 177
    "deck_missing": int(df_true['deck'].isna().sum()),     # 688
    "embarked_missing": int(df_true['embarked'].isna().sum()),  # 2
    "female_survival_pct": round(df_true[df_true['sex'] == 'female']['survived'].mean() * 100, 1),  # 74.2
    "male_survival_pct": round(df_true[df_true['sex'] == 'male']['survived'].mean() * 100, 1),      # 18.9
    "pclass1_survival_pct": round(df_true[df_true['pclass'] == 1]['survived'].mean() * 100, 1),     # 62.9
    "pclass2_survival_pct": round(df_true[df_true['pclass'] == 2]['survived'].mean() * 100, 1),     # 47.3
    "pclass3_survival_pct": round(df_true[df_true['pclass'] == 3]['survived'].mean() * 100, 1),     # 24.2
}


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_numbers(text):
    """Extract all floating-point numbers from a string."""
    return [float(m) for m in re.findall(r'\d+\.?\d*', text)]


def number_in_response(response, value, tolerance=0.5):
    """Check if a specific number appears in the agent's response."""
    numbers = extract_numbers(response)
    return any(abs(n - value) <= tolerance for n in numbers)


@pytest.fixture
def mock_st():
    """Mock streamlit across all project modules so tests run without Streamlit runtime."""
    with patch('agents.st'), patch('tools.st'), patch('visualization.st'), patch('utils.st'):
        yield


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def titanic_agent():
    """Create a DataAnalysisAgent for the Titanic dataset. Shared across tests."""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not found in .env — set it to run integration tests")

    df = pd.read_csv(csv_path)
    rp = ResponseProcessor(df)
    agent = DataAnalysisAgent(df, rp, api_key)
    agent.initialize_llm()
    agent.setup_agent(csv_path)
    return agent


# ── Fact-Checking Tests ────────────────────────────────────────────────────

@pytest.mark.integration
class TestFactualQueries:
    """Questions whose answers can be verified against ground truth."""

    def test_dataset_shape(self, titanic_agent, mock_st):
        """Q: 这个数据集有几行几列？"""
        response = titanic_agent.handle_chat_input(
            "这个数据集有几行几列？请用中文简短回答。"
        )
        assert str(GROUND_TRUTH["rows"]) in response, \
            f"Expected {GROUND_TRUTH['rows']} rows in response, got: {response[:200]}"
        assert str(GROUND_TRUTH["cols"]) in response, \
            f"Expected {GROUND_TRUTH['cols']} columns in response, got: {response[:200]}"

    def test_missing_values(self, titanic_agent, mock_st):
        """Q: 哪些列有缺失值，各缺了多少？"""
        response = titanic_agent.handle_chat_input(
            "哪些列有缺失值，各缺了多少？请列出具体数字。"
        )
        assert str(GROUND_TRUTH["age_missing"]) in response, \
            f"Expected age missing={GROUND_TRUTH['age_missing']}, got: {response[:300]}"
        assert str(GROUND_TRUTH["deck_missing"]) in response, \
            f"Expected deck missing={GROUND_TRUTH['deck_missing']}, got: {response[:300]}"

    def test_gender_survival_rates(self, titanic_agent, mock_st):
        """Q: 不同性别的存活率差异？"""
        response = titanic_agent.handle_chat_input(
            "不同性别（sex）的存活率（survived）有什么差异？给出具体百分比数字。"
        )
        assert number_in_response(response, GROUND_TRUTH["female_survival_pct"]), \
            f"Expected female survival ~{GROUND_TRUTH['female_survival_pct']}%, got: {response[:300]}"
        assert number_in_response(response, GROUND_TRUTH["male_survival_pct"]), \
            f"Expected male survival ~{GROUND_TRUTH['male_survival_pct']}%, got: {response[:300]}"

    def test_pclass_survival_rates(self, titanic_agent, mock_st):
        """Q: 不同舱位等级的存活率对比？"""
        response = titanic_agent.handle_chat_input(
            "不同舱位等级（pclass）的存活率对比是怎样的？给出具体百分比数字。"
        )
        assert number_in_response(response, GROUND_TRUTH["pclass1_survival_pct"]), \
            f"Expected pclass1 survival ~{GROUND_TRUTH['pclass1_survival_pct']}%"
        assert number_in_response(response, GROUND_TRUTH["pclass3_survival_pct"]), \
            f"Expected pclass3 survival ~{GROUND_TRUTH['pclass3_survival_pct']}%"


# ── Visualization Tests ────────────────────────────────────────────────────

@pytest.mark.integration
class TestVisualizationQueries:
    """Questions that trigger matplotlib charts."""

    def test_histogram(self, titanic_agent, mock_st):
        """Q: 展示年龄的分布，画直方图。"""
        response = titanic_agent.handle_chat_input(
            "展示年龄（age）的分布情况，画一个直方图。"
        )
        # Visualizations may trigger tool execution; response should be meaningful
        assert len(response) > 30, f"Response too short: {response[:200]}"

    def test_bar_chart(self, titanic_agent, mock_st):
        """Q: 舱位等级存活率柱状图。"""
        response = titanic_agent.handle_chat_input(
            "不同舱位等级的存活率对比是怎样的？画一个柱状图。"
        )
        assert len(response) > 30, f"Response too short: {response[:200]}"

    def test_heatmap(self, titanic_agent, mock_st):
        """Q: 数值列的相关性热力图。"""
        response = titanic_agent.handle_chat_input(
            "画出所有数值列之间的相关性热力图。"
        )
        assert len(response) > 30, f"Response too short: {response[:200]}"


# ── Deep Analysis Tests ────────────────────────────────────────────────────

@pytest.mark.integration
class TestDeepAnalysis:
    """Open-ended analytical questions — verify the agent can reason."""

    def test_key_survival_factors(self, titanic_agent, mock_st):
        """Q: 性别和舱位等级哪个对存活率影响更大？"""
        response = titanic_agent.handle_chat_input(
            "分析性别（sex）和舱位等级（pclass）这两个因素中，哪个对存活率（survived）的影响更大？给出具体百分比数字。"
        )
        # Verify response contains key findings (numeric survival rates by group)
        assert number_in_response(response, GROUND_TRUTH["female_survival_pct"]), \
            f"Expected female survival ~{GROUND_TRUTH['female_survival_pct']}%, got: {response[:300]}"
        assert number_in_response(response, GROUND_TRUTH["male_survival_pct"]), \
            f"Expected male survival ~{GROUND_TRUTH['male_survival_pct']}%, got: {response[:300]}"

    def test_business_recommendations(self, titanic_agent, mock_st):
        """Q: 作为船运公司高管，应该优先做什么安全改进？"""
        response = titanic_agent.handle_chat_input(
            "假如我是船运公司的高管，这个数据告诉我在安全策略上应该优先做什么改进？请给出商业建议。"
        )
        assert len(response) > 150, \
            f"Expected substantial recommendations (>150 chars), got {len(response)} chars: {response[:200]}"

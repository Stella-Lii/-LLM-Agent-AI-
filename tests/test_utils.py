import pytest
from utils import CodeUtils


class TestExtractCodeFromResponse:
    """Tests for CodeUtils.extract_code_from_response — the core code extraction logic."""

    def test_extract_python_code_block(self):
        """Pattern 1: code inside ```python ... ``` block."""
        response = """Here is the result:

```python
import matplotlib.pyplot as plt
df['age'].plot(kind='hist')
```
Hope this helps!"""
        code = CodeUtils.extract_code_from_response(response)
        assert code is not None
        assert "df['age'].plot(kind='hist')" in code
        assert "plt.show()" not in code  # original code doesn't have it

    def test_extract_action_input_format(self):
        """Pattern 2: Action: python_repl_ast + Action Input format."""
        response = """Thought: I need to check the data
Action: python_repl_ast
Action Input: print(df.head())
Observation: ..."""
        code = CodeUtils.extract_code_from_response(response)
        assert code is not None
        assert "print(df.head())" in code

    def test_extract_df_plt_pattern(self):
        """Pattern 3: plain text containing df[] and .plot/.plt patterns."""
        response = """Let me show the age distribution.

df['age'].plot(kind='hist', bins=30)
plt.title('Age Distribution')
plt.xlabel('Age')

This shows the distribution of passenger ages."""
        code = CodeUtils.extract_code_from_response(response)
        assert code is not None
        assert "df['age'].plot" in code
        assert "plt.title" in code

    def test_no_code_returns_none(self):
        """Pure text with no code should return None."""
        response = "The dataset has 891 rows and 15 columns. No missing values were found."
        code = CodeUtils.extract_code_from_response(response)
        assert code is None

    def test_empty_response(self):
        """Empty string should return None."""
        assert CodeUtils.extract_code_from_response("") is None

    def test_extract_with_multiline_code(self):
        """Multi-line code block should be fully extracted."""
        response = """Here is the analysis:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Check correlations
corr = df.corr()
print(corr)

# Plot
plt.figure(figsize=(10, 8))
plt.imshow(corr)
```
"""
        code = CodeUtils.extract_code_from_response(response)
        assert code is not None
        assert "df.corr()" in code
        assert "plt.figure" in code
        assert "import pandas as pd" in code


class TestSanitizeCode:
    """Tests for CodeUtils.sanitize_code."""

    def test_removes_plt_show(self):
        code = "plt.plot([1,2,3])\nplt.show()\nprint('done')"
        sanitized = CodeUtils.sanitize_code(code)
        assert "plt.show()" not in sanitized
        assert "plt.plot([1,2,3])" in sanitized
        assert "print('done')" in sanitized

    def test_no_plt_show_unchanged(self):
        code = "df.describe()"
        assert CodeUtils.sanitize_code(code) == code

    def test_none_input(self):
        assert CodeUtils.sanitize_code(None) is None

    def test_empty_input(self):
        assert CodeUtils.sanitize_code("") == ""


class TestRemoveCodeFromResponse:
    """Tests for CodeUtils.remove_code_from_response."""

    def test_removes_python_block(self):
        response = """Before text.
```python
print('hello')
```
After text."""
        cleaned = CodeUtils.remove_code_from_response(response, "print('hello')")
        assert "```python" not in cleaned
        assert "print('hello')" not in cleaned
        assert "Before text" in cleaned
        assert "After text" in cleaned

    def test_removes_action_input_block(self):
        response = """Thought: checking
Action: python_repl_ast
Action Input: df.shape
Observation: (891, 15)
Final Answer: The dataset has 891 rows."""
        cleaned = CodeUtils.remove_code_from_response(response, "df.shape")
        assert "Action: python_repl_ast" not in cleaned
        assert "Action Input:" not in cleaned
        assert "Final Answer" in cleaned

    def test_preserves_non_code_content(self):
        response = """## Analysis Report

Here are the key findings:
- Finding 1: The data shows a strong correlation
- Finding 2: There are outliers in column X

```python
df.describe()
```

Thank you for your question!"""
        cleaned = CodeUtils.remove_code_from_response(response, "df.describe()")
        assert "Analysis Report" in cleaned
        assert "Finding 1" in cleaned
        assert "Finding 2" in cleaned
        assert "Thank you" in cleaned
        assert "```python" not in cleaned

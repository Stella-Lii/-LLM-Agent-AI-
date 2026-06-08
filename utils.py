import re
import streamlit as st


class CodeUtils:
    """Utility class for code extraction and execution"""

    @staticmethod
    def is_visualization_code(code):
        """Check if the code contains actual plotting commands."""
        if not code:
            return False
        plot_patterns = [r'\bplt\.', r'\bsns\.', r'\.plot\(', r'\.hist\(', r'\.scatter\(']
        return any(re.search(p, code) for p in plot_patterns)

    @staticmethod
    def extract_code_from_response(response):
        """Extract Python code from LLM response using various patterns"""
        # Pattern 1: Code within python code blocks
        pattern1 = r"```python\n(.*?)```"
        match1 = re.search(pattern1, response, re.DOTALL)
        if match1:
            code = match1.group(1).strip()
            if CodeUtils.is_visualization_code(code):
                return code
            return None

        # Pattern 2: Code from python_repl_ast Action Input
        pattern2 = r"Action: python_repl_ast\nAction Input: (.*?)(?=\n[A-Z]|$)"
        match2 = re.search(pattern2, response, re.DOTALL)
        if match2:
            code = match2.group(1).strip()
            if CodeUtils.is_visualization_code(code):
                return code
            return None

        # Pattern 3: Just look for the typical pandas/matplotlib patterns
        if "df[" in response and (".plot" in response or "plt." in response):
            lines = response.split('\n')
            code_lines = []
            capture = False

            for line in lines:
                if "df[" in line or "plt." in line or ".plot" in line:
                    capture = True

                if capture and line and line[0].isupper() and "." in line and not any(x in line for x in ["df", "plt", "pd", "np", "import"]):
                    break

                if capture and line.strip():
                    code_lines.append(line)

            if code_lines:
                return "\n".join(code_lines)

        return None

    @staticmethod
    def remove_code_from_response(response, code):
        """Remove the executed code from the response text"""
        cleaned = re.sub(r"```python\n.*?```", "", response, flags=re.DOTALL)
        cleaned = re.sub(r"Action: python_repl_ast\nAction Input: .*?(?=\n[A-Z]|$)", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\n\n+", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def sanitize_code(code):
        """Clean up code by removing plt.show() calls"""
        if not code:
            return code
        return re.sub(r'plt\.show\(\)', '', code)


class DataFrameUtils:
    """Utility class for dataframe operations"""

    @staticmethod
    def display_dataframe_info(df):
        """Display information about the dataframe."""
        st.markdown("<h3 style='text-align: center;'>数据集概览</h3>", unsafe_allow_html=True)
        with st.expander("查看样本数据"):
            st.dataframe(df.head(), use_container_width=True)

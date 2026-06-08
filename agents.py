import io
import os
import re
import matplotlib.pyplot as plt
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_experimental.agents import create_csv_agent

from utils import CodeUtils
from tools import CustomPythonAstREPLTool
from visualization import VisualizationHandler

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def _load_prompt(filename):
    """Load a prompt template from the prompts/ directory."""
    with open(os.path.join(_PROMPTS_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


class ResponseProcessor:
    """Class to process and execute Python code from agent responses"""

    def __init__(self, df):
        self.df = df
        self.visualization_executed = False

    def process_response(self, response):
        """Process agent response to execute Python code visualizations."""

        if self.visualization_executed:
            self.visualization_executed = False
            return response

        python_code = CodeUtils.extract_code_from_response(response)

        if python_code:
            try:
                success, message = VisualizationHandler.execute_visualization_code(python_code, self.df)

                if success:
                    self.visualization_executed = True

                cleaned_response = CodeUtils.remove_code_from_response(response, python_code)
                return cleaned_response
            except Exception as e:
                st.error(f"Error executing Python code: {str(e)}")

        return response


class LLMAgent:
    """Base class for LLM agents with common functionality"""

    COMMON_SYSTEM_TEMPLATE = _load_prompt("base_analyst.md")

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.llm = None

    def initialize_llm(self):
        """Initialize the LLM with DeepSeek API"""
        if not self.api_key:
            return False

        try:
            self.llm = ChatOpenAI(
                model="deepseek-v4-flash",
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
                temperature=0.7,
                max_tokens=4096,
                timeout=120,
                max_retries=2
            )
            return True
        except Exception as e:
            st.error(f"Error initializing DeepSeek LLM: {str(e)}")
            return False


class DataAnalysisAgent(LLMAgent):
    """Class to handle LLM agent interactions for data analysis"""

    SYSTEM_TEMPLATE = _load_prompt("base_analyst.md") + _load_prompt("csv_agent.md")

    def __init__(self, df, response_processor, api_key=None):
        super().__init__(api_key)
        self.df = df
        self.response_processor = response_processor
        self.agent = None

    def setup_agent(self, file_path):
        """Set up the CSV agent with DeepSeek LLM."""
        df_schema = "\n".join([f"- {col} ({self.df[col].dtype})" for col in self.df.columns])
        system_prompt = self.SYSTEM_TEMPLATE.format(df_schema=df_schema)

        if not self.llm and not self.initialize_llm():
            return None

        try:
            python_repl_tool = CustomPythonAstREPLTool(locals=VisualizationHandler.get_execution_context(self.df))

            self.agent = create_csv_agent(
                self.llm,
                file_path,
                verbose=True,
                agent_type="tool-calling",
                prefix=system_prompt,
                allow_dangerous_code=True,
                extra_tools=[python_repl_tool],
                max_iterations=15,
                max_execution_time=180,
                early_stopping_method="force",
                agent_executor_kwargs={"handle_parsing_errors": True}
            )

            return self.agent

        except Exception as e:
            st.error(f"Error setting up the agent: {str(e)}")
            return None

    @staticmethod
    def _build_contextual_prompt(prompt, chat_history=None):
        """Build prompt with prior conversation context for multi-turn dialogue."""
        if not chat_history or len(chat_history) <= 1:
            return prompt

        recent = chat_history[:-1][-10:]
        if not recent:
            return prompt

        context_lines = ["以下是之前的对话记录：", ""]
        for msg in recent:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            context_lines.append(f"**{role}**: {content}")
            context_lines.append("")

        context_lines.append("---")
        context_lines.append(f"基于以上对话上下文，请回答用户的最新问题：\n\n{prompt}")
        return "\n".join(context_lines)

    def handle_chat_input(self, prompt, chat_history=None):
        """Process chat input and handle agent responses."""
        contextualized_prompt = self._build_contextual_prompt(prompt, chat_history)

        try:
            try:
                raw_response = self.agent.run(contextualized_prompt)
            except ValueError as e:
                error_msg = str(e)

                if any(phrase in error_msg for phrase in [
                    "Could not parse LLM output:",
                    "Parsing LLM output produced both a final answer and a parse-able action",
                    "An output parsing error occurred"
                ]):
                    raw_response = self._extract_response_from_error(error_msg)

                    if not raw_response:
                        raw_response = self._direct_llm_fallback(contextualized_prompt)
                else:
                    raw_response = self._direct_llm_fallback(contextualized_prompt)

            except Exception:
                raw_response = self._direct_llm_fallback(contextualized_prompt)

            if isinstance(raw_response, str) and "Agent stopped due to max iterations" in raw_response:
                raw_response = self._direct_llm_fallback(contextualized_prompt)

            if any(kw in prompt for kw in ["代码", "code", "Code"]):
                history = st.session_state.get("_tool_history", [])
                if history:
                    code_blocks = []
                    for i, entry in enumerate(history, 1):
                        code_blocks.append(f"**Step {i}:**\n```python\n{entry['code']}\n```\nOutput: {entry['result']}")
                    raw_response += "\n\n---\n## 执行代码记录\n\n" + "\n\n".join(code_blocks)
                else:
                    raw_response += "\n\n> 本次对话未通过工具执行代码，所有回答均为直接生成。"

            if plt.get_fignums():
                for fig_num in plt.get_fignums():
                    fig = plt.figure(fig_num)
                    st.pyplot(fig)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
                    buf.seek(0)
                    st.session_state.setdefault("_pending_figures", []).append(buf)
                    plt.close(fig)

            processed_response = self.response_processor.process_response(raw_response)
            st.write(processed_response)

            return raw_response

        except Exception as e:
            error_msg = str(e)
            st.error(f"Error processing your question: {error_msg}")

            if "agent_scratchpad" in error_msg:
                st.warning("The AI had difficulty processing your request with the available data.")
                st.info("Try asking a simpler question or provide more context.")

            return f"I encountered an error processing your request: {error_msg}"

    def _extract_response_from_error(self, error_msg):
        """Extract meaningful response from parsing error messages."""
        backtick_pattern = r"`([^`]+)`"
        matches = re.findall(backtick_pattern, error_msg)
        if matches:
            longest_match = max(matches, key=len)
            if len(longest_match) > 50:
                return longest_match

        parse_pattern = r"Could not parse LLM output:\s*(.+?)(?:\n\n|\Z)"
        match = re.search(parse_pattern, error_msg, re.DOTALL)
        if match:
            return match.group(1).strip()

        lines = error_msg.split('\n')
        content_lines = []
        capturing = False

        for line in lines:
            if any(phrase in line for phrase in ["analysis", "data", "findings", "results"]):
                capturing = True

            if capturing and line.strip():
                if not any(phrase in line.lower() for phrase in [
                    "error", "traceback", "exception", "could not parse", "parsing"
                ]):
                    content_lines.append(line)

        if content_lines:
            return '\n'.join(content_lines)

        return None

    def _direct_llm_fallback(self, prompt):
        """Direct LLM call as fallback when agent fails."""
        try:
            if not self.llm:
                return "I apologize, but I'm having technical difficulties processing your request."

            df_info = f"Dataset shape: {self.df.shape}\nColumns: {', '.join(self.df.columns[:10])}"
            if len(self.df.columns) > 10:
                df_info += f"... and {len(self.df.columns) - 10} more columns"

            fallback_prompt = f"""
            As a data analyst, please analyze this request: "{prompt}"

            Dataset Information:
            {df_info}

            Please provide a comprehensive analysis with:
            1. Executive Summary
            2. Analysis approach
            3. Key insights based on the request
            4. Recommendations
            5. Next steps

            Note: I cannot execute code directly in this mode, so focus on analytical insights and methodology.
            """

            response = self.llm.invoke(fallback_prompt)

            fallback_response = f"""
## Analysis Report (Direct Mode)

*Note: This analysis was generated in direct mode due to technical constraints. For interactive visualizations and code execution, please try rephrasing your question.*

{response.content if hasattr(response, 'content') else str(response)}
            """

            return fallback_response

        except Exception as e:
            return f"""
## Analysis Error

I apologize, but I encountered technical difficulties processing your request.

**Error Details:** {str(e)}

**Suggestions:**
1. Try rephrasing your question in simpler terms
2. Break complex requests into smaller parts
3. Ensure your CSV data is properly formatted
4. Check if the column names in your question match the dataset

**Available Columns:** {', '.join(self.df.columns[:5])}{'...' if len(self.df.columns) > 5 else ''}
            """


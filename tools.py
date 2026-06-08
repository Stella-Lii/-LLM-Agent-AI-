import io
import matplotlib.pyplot as plt
import streamlit as st
from langchain_experimental.tools import PythonAstREPLTool


class CustomPythonAstREPLTool(PythonAstREPLTool):
    """Custom Python AST REPL Tool that captures and displays matplotlib figures in Streamlit"""

    name: str = "custom_python_repl_ast"
    description: str = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "When using this tool, sometimes output is abbreviated - "
        "make sure you do not stop before getting the full output."
    )

    @staticmethod
    def _save_figure_to_session(fig):
        """Persist a matplotlib figure to session state for history replay."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        st.session_state.setdefault("_pending_figures", []).append(buf)

    def _run(self, query: str) -> str:
        """Run the query in the Python REPL and capture the result."""
        try:
            if self.locals is None:
                self.locals = {}

            result = super()._run(query)

            st.session_state.setdefault("_tool_history", []).append({
                "code": query,
                "result": result[:500],
            })

            if plt.get_fignums():
                current_fig = plt.gcf()
                st.pyplot(current_fig)
                self._save_figure_to_session(current_fig)
                plt.close(current_fig)
                result += "\n\nVisualization successfully displayed."

            return result

        except Exception as e:
            error_message = f"Error executing code: {str(e)}"
            st.error(error_message)
            return error_message

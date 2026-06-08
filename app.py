import os
import atexit
import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv

from utils import DataFrameUtils
from agents import DataAnalysisAgent, ResponseProcessor

# Load environment variables
load_dotenv()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # kept for backward compatibility


class DataApp:
    """Main application class that orchestrates all components"""

    def __init__(self):
        self.df = None
        self.file_path = None
        self.response_processor = None
        self.analysis_agent = None
        atexit.register(self._cleanup_temp_file)

    def _cleanup_temp_file(self):
        """Remove the temporary CSV file if it exists."""
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.unlink(self.file_path)
            except OSError:
                pass  # best-effort cleanup

    def process_uploaded_file(self, file, api_key=None):
        """Process the uploaded CSV file and return dataframe and file path."""
        with st.spinner("正在加载数据集..."):
            try:
                # Clean up previous temp file before creating a new one
                self._cleanup_temp_file()

                with NamedTemporaryFile(delete=False) as f:
                    f.write(file.getbuffer())
                    self.file_path = f.name

                try:
                    self.df = pd.read_csv(self.file_path)
                except Exception as e:
                    st.error(f"读取 CSV 文件失败：{str(e)}")
                    st.info("请确保文件是格式正确的有效 CSV 文件。")
                    return None

                self.response_processor = ResponseProcessor(self.df)
                self.analysis_agent = DataAnalysisAgent(self.df, self.response_processor, api_key)

                return self.df

            except Exception as e:
                st.error(f"处理文件失败：{str(e)}")
                return None

    def run(self):
        """Run the main application"""
        st.set_page_config(
            page_title="Analyzia - AI 智能数据分析",
            page_icon="",
            layout="centered",
            initial_sidebar_state="expanded",
            menu_items={
                'About': "Analyzia - AI 智能数据分析平台"
            }
        )

        # Hide Streamlit default elements for cleaner look
        st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}

        header[data-testid="stHeader"] {
            background-color: transparent;
        }

        .css-1d391kg {display: block !important;}
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
        }

        .main .block-container {
            padding-top: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 800px;
        }

        .stChatMessage {
            background-color: transparent;
            border: none;
        }

        .stChatInputContainer {
            max-width: 800px;
            margin: 0 auto;
        }

        div[data-testid="stChatInputContainer"] {
            max-width: 800px !important;
            margin: 0 auto !important;
            padding: 0 1rem;
        }

        div[data-testid="stChatInputContainer"] > div {
            max-width: 100% !important;
        }

        button[data-testid="collapsedControl"] {
            display: block !important;
            visibility: visible !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Sidebar
        with st.sidebar:
            st.markdown("""
            <style>
            .css-1lcbmhc.e1fqkh3o0 {
                width: 250px !important;
                min-width: 250px !important;
            }
            .css-17eq0hr {
                padding: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown("# Analyzia")
            st.markdown("*AI 智能数据分析*")
            st.markdown("---")

            st.markdown("### API 配置")
            if DEEPSEEK_API_KEY:
                st.success("DeepSeek API Key 已配置")
                api_key = DEEPSEEK_API_KEY
            elif GOOGLE_API_KEY:
                st.success("Google API Key 已配置")
                api_key = GOOGLE_API_KEY
            else:
                api_key = st.text_input("DeepSeek API Key", type="password", placeholder="请输入 API Key...")

            st.markdown("---")

            st.markdown("### 数据上传")
            uploaded_file = st.file_uploader("点击或拖拽上传 CSV 文件", type=["csv"])

        # Initialize or reset session state
        if 'messages' not in st.session_state:
            st.session_state.messages = []

        # Restore persisted state from session
        if 'df' in st.session_state:
            self.df = st.session_state.df
            self.file_path = st.session_state.file_path
            self.response_processor = st.session_state.response_processor
            self.analysis_agent = st.session_state.analysis_agent

        # Process file if uploaded and it's a new file
        if uploaded_file and (self.df is None or uploaded_file.name != st.session_state.get('last_file', '')):
            self.process_uploaded_file(uploaded_file, api_key)
            if self.df is not None:
                st.session_state.last_file = uploaded_file.name
                st.session_state.df = self.df
                st.session_state.file_path = self.file_path
                st.session_state.response_processor = self.response_processor
                st.session_state.analysis_agent = self.analysis_agent
                st.session_state.messages = []

        # Setup agent if conditions are met
        if self.df is not None and api_key:
            if self.analysis_agent and self.analysis_agent.agent is None:
                self.analysis_agent.api_key = api_key
                self.analysis_agent.setup_agent(self.file_path)
                st.session_state.analysis_agent = self.analysis_agent

        # Main content area
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0 2rem 0;">
            <h1 style="margin-bottom: 0.5rem; font-size: 3rem; font-weight: bold;">Analyzia</h1>
            <p style="color: #666; font-size: 1.1rem; margin: 0;">
                AI 智能数据分析平台
            </p>
        </div>
        """, unsafe_allow_html=True)

        if self.df is not None:
            DataFrameUtils.display_dataframe_info(self.df)

        # Status prompts
        if not uploaded_file and not api_key:
            st.markdown("""
            <div style="text-align: center; padding: 1rem 0;">
                <p style="color: #0066cc; background-color: #e6f3ff; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #0066cc; margin: 0 auto; max-width: 600px;">
                请在侧边栏上传 CSV 文件并输入 API Key
                </p>
            </div>
            """, unsafe_allow_html=True)
        elif not uploaded_file:
            st.markdown("""
            <div style="text-align: center; padding: 1rem 0;">
                <p style="color: #0066cc; background-color: #e6f3ff; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #0066cc; margin: 0 auto; max-width: 600px;">
                    请在侧边栏上传 CSV 文件开始分析
                </p>
            </div>
            """, unsafe_allow_html=True)
        elif not api_key:
            st.markdown("""
            <div style="text-align: center; padding: 1rem 0;">
                <p style="color: #0066cc; background-color: #e6f3ff; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #0066cc; margin: 0 auto; max-width: 600px;">
                    请在侧边栏输入 DeepSeek API Key 开始分析数据
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Chat messages container
        chat_container = st.container()

        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    for fig_buf in message.get("figures", []):
                        st.image(fig_buf)

        # Chat input
        if prompt := st.chat_input("输入你的问题..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                if not uploaded_file:
                    response = """
未找到数据集

我还没有看到你上传任何数据集。

请按以下步骤开始：
1. 在侧边栏上传 CSV 文件
2. 在侧边栏输入 DeepSeek API Key
3. 重新发送你的问题

上传数据后，我可以帮你完成以下分析：
- 数据探索与汇总
- 统计分析与相关性研究
- 专业图表与可视化
- 商业洞察与建议
                    """
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                elif not api_key:
                    response = """
需要 API Key

我已看到你的数据集，但需要 DeepSeek API Key 才能开始分析。

请继续操作：
1. 在侧边栏输入你的 DeepSeek API Key（可在 https://platform.deepseek.com 获取）
2. 重新发送你的问题

你的数据已就绪，只需要 API Key 即可开始分析！
                    """
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                elif self.analysis_agent and self.analysis_agent.agent:
                    st.session_state["_pending_figures"] = []
                    st.session_state["_tool_history"] = []
                    response = self.analysis_agent.handle_chat_input(
                        prompt,
                        chat_history=st.session_state.messages
                    )
                    figures = st.session_state.pop("_pending_figures", [])
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "figures": figures,
                    })

                else:
                    response = """
配置异常

分析系统似乎遇到了配置问题，请尝试：

1. 刷新页面
2. 重新上传 CSV 文件
3. 重新输入 API Key
4. 重新发送你的问题

如果问题仍然存在，请检查 API Key 是否有效、CSV 文件格式是否正确。
                    """
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    app = DataApp()
    app.run()

import os

os.environ["ENABLE_MOCK_MODEL"] = "1"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("TAVILY_API_KEY", None)

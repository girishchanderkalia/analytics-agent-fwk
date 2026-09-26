from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'agent-runtime'))
from mcp_tools import McpToolDescriptor,McpToolRegistry,MCPToolResult,MCPServerRegistration
def test_coherent_imports(): assert all((McpToolDescriptor,McpToolRegistry,MCPToolResult,MCPServerRegistration))

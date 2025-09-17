# ────────────────────────────────────────────────────────────────────────────────
# Helper – convert every ToolBase instance into an Agent‑SDK FunctionTool
# ────────────────────────────────────────────────────────────────────────────────
import json

from agents import FunctionTool, RunContextWrapper

from shared.agent_manager.ai_tools.tool_base import ToolBase
from shared.agent_manager.ai_tools.tools_manager import ToolsManager


def _tool_to_function_tool(tool_instance: ToolBase) -> FunctionTool:
    """
    Wraps a ToolBase instance (e.g. BookSearch, BookData, …) into an
    Agent‑SDK FunctionTool on‑the‑fly.  The generated FunctionTool:

    • keeps the original schema (ToolBase.generate_schema)
    • forwards *all* arguments to tool.execute(**kwargs)
    • supports both sync + async execute implementations
    """

    schema = tool_instance.generate_schema()["function"]

    async def on_invoke_tool(
            wrapper: RunContextWrapper,
            args_json: str
    ):
        # 1. parse the JSON the LLM sent us
        kwargs = json.loads(args_json)

        # 2. extract your runtime context from wrapper.context
        #    (must be an object with attrs tenant_id, thread, tenant)
        ctxt = wrapper.context
        tenant_id = ctxt.tenant_id
        thread = ctxt.thread
        tenant = ctxt.tenant

        # 3. delegate to your ToolsManager
        result = await ToolsManager().execute_tool(
            tool_name=tool_instance.name,
            params=kwargs,
            tenant_id=tenant_id,
            thread=thread,
            tenant=tenant,
        )

        # 4. turn it into something JSON‐friendly
        if isinstance(result, str):
            return result
        return json.dumps(result, default=str)

    return FunctionTool(
        name=schema["name"],
        description=schema["description"],
        params_json_schema=schema["parameters"],
        on_invoke_tool=on_invoke_tool,
        strict_json_schema=True,
    )
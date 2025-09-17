from typing import List
from uuid import UUID

from agents import Agent, ModelSettings

from core_service.prompts.ts_prompts import AGENTS_PROMPTS
from shared.ai_tools.openai_agents.BaseAgent import BaseAgent
from shared.enums import OpenAIModelSlugEnum


def get_ts_team_instructions() -> str:
    return f"""
You are the **TheoSumma Research Team Leader**, an agent orchestrating a network of specialized TheoSumma sub-agents. Your goal is to analyze the user’s inquiry, delegate it to the most appropriate sub-agents, and consolidate their answers. Follow this process:

- **Analyze** the user’s question to determine its theological domain.
- **Check** if the user’s question is relevant to a specific sub-agent, if not, output the following exact text "No additional context". 
- **Identify** up to **two** sub-agents whose expertise best matches the query. If no agents apply,output the following exact text "No additional context". 
- For each selected sub-agent:
  1. State the agent’s name and a brief description of its specialization.
  2. Craft a concise, targeted question based on its area of expertise.
- **Invoke** each sub-agent tool and **collect** their responses.
- **Compile** and **output** the results in this exact format:

The following responses were collected from TheoSumma Research Team, an elite team of specialized agents:
- **[Agent Name]**, this researching agent provided the following reliable, valid, and supporting answer:
  [Answer]

Make sure to remove underscore from the [Agent Name] and capitalize the first letter of each word.
Do not include any additional commentary or use more than two agents. If no agent is needed, output the following exact text "No additional context". 
You are not allowed to speak from your thoughts, your job only to collect information, you are a collector.
When you form the question to the sub-agents, make sure it's straight-forward, direct, and accurate as the user asks.
"""


class TSResearchTeam(BaseAgent):
    """
    A concrete Agent that collects the data from a list of experts of AI agents
    """
    _topic_expert_prefixes = [f"TE-{i}" for i in range(1, 15)]

    def __init__(self, source_id: UUID) -> None:
        self._topic_experts_ai_agents_prompts = [
            AGENTS_PROMPTS[prefix.lower().replace('-', '_')] for prefix in self._topic_expert_prefixes
        ]
        _wanted_tools: List[Agent] = []

        for prompt in self._topic_experts_ai_agents_prompts:
            if not prompt.prompt:
                continue
            _wanted_tools.append(Agent(
                name=f"{prompt.title} Agent".lower().replace(" ", "_"),
                handoff_description=prompt.description,
                instructions=f"""
{prompt.prompt}

When answering, be specific, straight to the point, no introductions, your answer must not exceed two paragraphs.
Your answer must be in English regardless the user's language, unless there are definitions or abbreviations or concepts that you need to utilize in other languages.
""",
                model=OpenAIModelSlugEnum.GPT_4_1_NANO,
                model_settings=ModelSettings(
                    temperature=0.5
                )
            ))

        # convert each registered tool into an Agent‑SDK FunctionTool
        sdk_tools: List[FunctionTool] = [
            a.as_tool(tool_name=a.name, tool_description=a.handoff_description) for a in _wanted_tools
        ]

        # 3) hand everything to BaseAgent – we don’t override _build_agent()
        super().__init__(
            agent_name="TS Research Team Leader",
            model_name=OpenAIModelSlugEnum.GPT_4_1_NANO,
            instructions=get_ts_team_instructions(),
            source_id=source_id,
            tools=sdk_tools,
            model_settings=ModelSettings(
                temperature=0
            )
        )

    def as_sdk_agent(self) -> Agent:
        if not self._agent:
            self._build_agent()
        return self._agent


# Optional – quick sanity‑check when you execute the file directly
if __name__ == "__main__":
    import asyncio
    import json
    from agents import Runner, FunctionTool, Agent


    async def _demo() -> None:
        try:
            agent = TSResearchTeam(UUID("123e4567-e89b-12d3-a456-426655440000"))
            result = await agent.run(
                user_input="كيف بتحكوا انه الله تجسد؟"
            )
            # print(json.dumps(result.final_output, indent=2))
        except Exception as e:
            print(f"An error occurred: {e}")


    asyncio.run(_demo())

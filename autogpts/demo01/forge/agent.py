from forge.actions import ActionRegister
from forge.sdk import (
    Agent,
    AgentDB,
    ForgeLogger,
    Step,
    StepRequestBody,
    Task,
    TaskRequestBody,
    Workspace,
)
from .sdk import PromptEngine
from jinja2 import Environment, FileSystemLoader

# 初始化 Jinja2 环境
file_loader = FileSystemLoader('path/to/templates')
env = Environment(loader=file_loader)

# 加载模板
template = env.get_template('template.jinja')

# 渲染模板
prompt = template.render(task_description=task['description'], task_input=task['input'])

# 使用渲染的提示进行进一步操作
print(prompt)


LOG = ForgeLogger(__name__)


class ForgeAgent(Agent):
    """
    The goal of the Forge is to take care of the boilerplate code, so you can focus on
    agent design.

    There is a great paper surveying the agent landscape: https://arxiv.org/abs/2308.11432
    Which I would highly recommend reading as it will help you understand the possabilities.

    Here is a summary of the key components of an agent:

    Anatomy of an agent:
         - Profile
         - Memory
         - Planning
         - Action

    Profile:

    Agents typically perform a task by assuming specific roles. For example, a teacher,
    a coder, a planner etc. In using the profile in the llm prompt it has been shown to
    improve the quality of the output. https://arxiv.org/abs/2305.14688

    Additionally, based on the profile selected, the agent could be configured to use a
    different llm. The possibilities are endless and the profile can be selected
    dynamically based on the task at hand.

    Memory:

    Memory is critical for the agent to accumulate experiences, self-evolve, and behave
    in a more consistent, reasonable, and effective manner. There are many approaches to
    memory. However, some thoughts: there is long term and short term or working memory.
    You may want different approaches for each. There has also been work exploring the
    idea of memory reflection, which is the ability to assess its memories and re-evaluate
    them. For example, condensing short term memories into long term memories.

    Planning:

    When humans face a complex task, they first break it down into simple subtasks and then
    solve each subtask one by one. The planning module empowers LLM-based agents with the ability
    to think and plan for solving complex tasks, which makes the agent more comprehensive,
    powerful, and reliable. The two key methods to consider are: Planning with feedback and planning
    without feedback.

    Action:

    Actions translate the agent's decisions into specific outcomes. For example, if the agent
    decides to write a file, the action would be to write the file. There are many approaches you
    could implement actions.

    The Forge has a basic module for each of these areas. However, you are free to implement your own.
    This is just a starting point.
    """

    def __init__(self, database: AgentDB, workspace: Workspace):
        """
        The database is used to store tasks, steps and artifact metadata. The workspace is used to
        store artifacts. The workspace is a directory on the file system.

        Feel free to create subclasses of the database and workspace to implement your own storage
        """
        super().__init__(database, workspace)
        self.abilities = ActionRegister(self)

    async def create_task(self, task_request: TaskRequestBody) -> Task:
        """
        The agent protocol, which is the core of the Forge, works by creating a task and then
        executing steps for that task. This method is called when the agent is asked to create
        a task.

        We are hooking into function to add a custom log message. Though you can do anything you
        want here.
        """
        task = await super().create_task(task_request)
        LOG.info(
            f"📦 Task created: {task.task_id} input: {task.input[:40]}{'...' if len(task.input) > 40 else ''}"
        )
        return task

    async def execute_step(self, task_id: str, step_request: StepRequestBody) -> Step:
        # 获取任务
        task = await self.db.get_task(task_id)

        # 创建步骤
        step = await self.db.create_step(
            task_id=task_id, input=step_request, is_last=True
        )

        # 加载并渲染提示模板
        template = Environment.get_template('template.jinja')
        system_prompt = "This is the system prompt."
        task_prompt = template.render(task_description=task['description'], task_input=task['input'])

        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt}
        ]

        try:
            # 定义 chat completion 请求的参数
            chat_completion_kwargs = {
                "messages": messages,
                "model": "gpt-3.5-turbo",
            }
            # 发出 chat completion 请求并解析响应
            chat_response = await chat_completion_request(**chat_completion_kwargs)
            answer = json.loads(chat_response["choices"][0]["message"]["content"])

            # 记录答案以便调试
            LOG.info(pprint.pformat(answer))

        except json.JSONDecodeError as e:
            # 处理 JSON 解码错误
            LOG.error(f"无法解码聊天响应: {chat_response}")
        except Exception as e:
            # 处理其他异常
            LOG.error(f"无法生成聊天响应: {e}")



        return step
    
    @ability(
        name="write_file",
        description="Write data to a file",
        parameters=[
            {
                "name": "file_path",
                "description": "Path to the file",
                "type": "string",
                "required": True,
            },
            {
                "name": "data",
                "description": "Data to write to the file",
                "type": "bytes",
                "required": True,
            },
        ],
        output_type="None",
    )
    async def write_file(agent, task_id: str, file_path: str, data: bytes) -> None:
        pass



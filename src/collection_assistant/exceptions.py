"""Custom exceptions."""


class CustomerNotFoundError(Exception):
    def __init__(self, customer_id: str):
        super().__init__(f"Customer {customer_id} not found")
        self.customer_id = customer_id


class AccountNotFoundError(Exception):
    def __init__(self, account_id: str):
        super().__init__(f"Account {account_id} not found")
        self.account_id = account_id


class WorkflowNotFoundError(Exception):
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow {workflow_id} not found")
        self.workflow_id = workflow_id


class LLMProviderError(Exception):
    pass


class AgentExecutionError(Exception):
    def __init__(self, agent_name: str, reason: str):
        super().__init__(f"Agent {agent_name} failed: {reason}")
        self.agent_name = agent_name

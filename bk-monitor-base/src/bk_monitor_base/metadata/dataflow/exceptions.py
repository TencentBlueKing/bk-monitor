class DataFlowException(Exception):
    pass


class DataFlowNotExists(DataFlowException):
    pass


class DataFlowStartFailed(DataFlowException):
    pass


class DataFlowNodeUpdateFailed(DataFlowException):
    pass


class DataFlowNodeCreateFailed(DataFlowException):
    pass

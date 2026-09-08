class CreateStrategyError(Exception):
    pass


class StrategyNotExistError(Exception):
    pass


class FunctionNotFoundError(Exception):
    pass


class FunctionNotSupportedError(Exception):
    pass


class ParamRequiredError(Exception):
    pass


class MultipleTimeAggregateFunctionError(Exception):
    pass

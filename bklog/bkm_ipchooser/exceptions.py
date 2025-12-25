class IpChooserBaseException(Exception):
    pass


class SerValidationError(IpChooserBaseException):
    pass


class TopoNotExistsError(IpChooserBaseException):
    pass


class BeyondTheSelectionRangeError(IpChooserBaseException):
    pass

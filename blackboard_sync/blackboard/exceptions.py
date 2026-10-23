class BBStatusError(Exception):
    def __init__(self, response: object):
        self.response = response
        text = getattr(response, "text", None)
        status_code = getattr(response, "status_code", None)
        super().__init__(text or f"Blackboard API error ({status_code or response})")


class BBBadRequestError(BBStatusError):
    pass


class BBUnauthorizedError(BBStatusError):
    pass


class BBForbiddenError(BBStatusError):
    pass

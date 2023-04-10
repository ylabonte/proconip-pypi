"""Defines various data structures."""


class ConfigObject:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url
        self.username = username
        self.password = password


from dataclasses import dataclass


@dataclass
class UserDTO:
    id: int
    username: str
    email: str
    is_active: bool
    email_verified: bool
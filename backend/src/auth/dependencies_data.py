# from .dependencies import RoleChecker
from fastapi import Depends
# from src.db.db_models import MemberRoleEnum

'''
This checks the role in the token details of the user, but since that may be edited by the user,
possibly do an async check in the db/redis to see if the user has the required permissions to access specified resources
'''

# role_checker = Depends(RoleChecker([MemberRoleEnum.USER, MemberRoleEnum.ADMIN, MemberRoleEnum.VIP]))

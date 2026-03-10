from .dependencies import RoleChecker
from fastapi import Depends
# from src.db.db_enum_models import MemberRoleEnum


# role_checker = Depends(RoleChecker([MemberRoleEnum.MEMBER]))
# admin_rolechecker = Depends(RoleChecker([MemberRoleEnum.ADMIN]))
# coach_rolechecker = Depends(RoleChecker([MemberRoleEnum.ADMIN, MemberRoleEnum.COACH]))
# officer_rolechecker = Depends(RoleChecker([MemberRoleEnum.ADMIN, MemberRoleEnum.OFFICER]))
# member_rolechecker = Depends(RoleChecker([MemberRoleEnum.ADMIN, MemberRoleEnum.COACH, MemberRoleEnum.OFFICER, MemberRoleEnum.MEMBER]))
# general_member_rolechecker = Depends(RoleChecker([MemberRoleEnum.ADMIN, MemberRoleEnum.COACH, MemberRoleEnum.OFFICER, MemberRoleEnum.MEMBER, MemberRoleEnum.INACTIVE, MemberRoleEnum.ALUMNI]))
# public_rolechecker = Depends(RoleChecker([role for role in MemberRoleEnum]))
from django.apps import AppConfig


# 클래스 이름도 UserAccountConfig로 변경하는 것을 권장합니다.
class UserAccountConfig(AppConfig):
    name = 'users'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'User Account Management' # 선택 사항
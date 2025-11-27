from django.shortcuts import render, redirect
from django.contrib.auth import logout # Django의 내장 로그아웃 함수 임포트
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.contrib.auth import login as auth_login
import random
from django.contrib.auth.decorators import login_required # 인증이 필요하다면 주석 해제
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from allauth.socialaccount.models import SocialAccount

def home(request):
    """
    메인 페이지를 렌더링하는 뷰입니다.
    최상위 templates/home.html 파일을 렌더링하고 로그인 상태를 템플릿에 전달합니다.
    """
    # 사용자의 로그인 상태를 확인합니다.
    # request.user 객체가 존재하는지 확인하는 방어적 코드입니다.
    is_logged_in = request.user.is_authenticated if hasattr(request, 'user') else False
    
    context = {
        'page_title': 'Tripsnap 메인 페이지',
        'is_logged_in': is_logged_in
    }
    # 템플릿 경로는 최상위 templates 디렉토리의 'home.html'을 사용합니다.
    return render(request, 'home.html', context)


# @login_required # 로그인한 사용자만 접근 가능하도록 하려면 이 데코레이터를 사용합니다.
def user_profile(request):
    """
    사용자 프로필 페이지를 렌더링하는 뷰입니다.
    실제 프로젝트에서는 request.user를 이용해 DB에서 사용자 데이터를 가져와야 합니다.
    """
    context = {
        'page_title': 'My Profile',
        # 여기에 실제 사용자 데이터를 담아 템플릿으로 전달합니다.
        # 'user_data': request.user 
    }
    return render(request, 'user/profile.html', context)

def login(request):
    """
    로그인 페이지 템플릿을 렌더링합니다.
    (실제 인증 처리는 allauth가 담당하며, 이 뷰는 템플릿만 보여줍니다.)
    """
    return render(request, 'user/login.html')

def signup(request):

    if request.user.is_authenticated:
        return redirect('users:home')
    if request.method == 'POST':
      form = CustomUserCreationForm(request.POST)
      if form.is_valid():
          user = form.save()
          user.backend = 'django.contrib.auth.backends.ModelBackend'
          # 자동 로그인 되어 메인 페이지로 돌아감
          auth_login(request, user)
          return redirect('users:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'user/signup.html', {'form':form})


@login_required
@require_http_methods(["POST"])
def account_delete(request):
    """
    사용자 계정 탈퇴 처리
    - 로그인된 사용자만 접근 가능
    - POST 요청만 허용
    - 소셜 계정 연결도 함께 삭제
    """
    user = request.user
    
    try:
        # 1. 소셜 계정 연결 삭제 (카카오 등)
        SocialAccount.objects.filter(user=user).delete()
        
        # 2. 로그아웃 처리 (세션 및 쿠키 삭제)
        logout(request)
        
        # 3. 사용자 계정 삭제 (연관된 Profile도 CASCADE로 자동 삭제됨)
        user.delete()
        
        messages.success(request, '계정이 성공적으로 탈퇴되었습니다.')
        
        # 4. 응답과 함께 쿠키 삭제
        response = redirect('/')
        response.delete_cookie('jwt-auth')
        response.delete_cookie('jwt-refresh')
        response.delete_cookie('sessionid')
        response.delete_cookie('csrftoken')
        
        return response
        
    except Exception as e:
        messages.error(request, f'탈퇴 처리 중 오류가 발생했습니다: {str(e)}')
        return redirect('/')


@login_required
def profile_view(request):
    """
    사용자 프로필 페이지
    User 모델의 모든 정보와 연결된 소셜 계정 정보를 표시
    """
    user = request.user
    
    # Profile 객체가 없으면 생성 (OneToOne 관계)
    try:
        profile = user.profile
    except:
        from .models import Profile
        profile = Profile.objects.create(user=user)
    
    context = {
        'user': user,
        'profile': profile,
    }
    
    return render(request, 'users/profile.html', context)
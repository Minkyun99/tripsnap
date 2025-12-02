from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone

from allauth.socialaccount.models import SocialAccount


import json
import base64
import uuid
import random

from django.core.files.base import ContentFile

from .forms import CustomUserCreationForm
from .models import User, Profile, Post, Like, Comment, Social

from django.http import JsonResponse

from django.db.models import Q

User = get_user_model()

def home(request):
    """
    메인 페이지
    """
    is_logged_in = request.user.is_authenticated if hasattr(request, 'user') else False

    context = {
        'page_title': 'Tripsnap 메인 페이지',
        'is_logged_in': is_logged_in
    }
    return render(request, 'home.html', context)


def login(request):
    """
    로그인 페이지 템플릿 렌더링 (인증은 allauth가 처리)
    """
    return render(request, 'user/login.html')

# 랜덤 닉네임 생성 함수
def generate_unique_nickname():
    adjectives = ['따뜻한', '뜨거운', '갓 구운', '신선한', '폭신한', '보송보송한', 
                          '쫄깃한', '바삭한', '파삭한', '부드러운', '촉촉한', '퍽퍽한', 
                          '거친', '묵직한', '고소한', '달콤한', '담백한', '짭짤한', 
                          '신맛이 나는', '시큼한', '풍부한', '향긋한', '노릇노릇한', 
                          '탐스러운', '먹음직스러운', '마른', '딱딱한', '매끈한', '겉바속촉', '눅눅한']
    nouns = ['밀가루', '효모', '이스트', '버터', '우유', '설탕', '소금', '계란', 
                     '반죽', '오븐', '베이커리', '빵집', '제빵사', '식빵', '바게트', 
                     '크루아상', '베이글', '모닝빵', '도넛', '케이크', '사워도우', 
                     '깜빠뉴', '크러스트', '겉껍질', '속살', '빵조각', '기포', '트레이']

    while True:
        nickname = f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 999)}"
        if not User.objects.filter(nickname=nickname).exists():
            return nickname
        
def signup(request):

    if request.user.is_authenticated:
        return redirect('users:home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # username 자동 생성 (옵션)
            if not user.username:
                user.username = user.email.split('@')[0]

            # 닉네임 랜덤 생성
            if not user.nickname or user.nickname.strip() == "":
                user.nickname = generate_unique_nickname()

            user.save()
            auth_login(request, user)

            return redirect('users:home')

    else:
        form = CustomUserCreationForm()
    return render(request, 'account/signup.html', {'form': form})




@login_required
@require_http_methods(["POST"])
def account_delete(request):
    """
    사용자 계정 탈퇴
    """
    user = request.user

    try:
        SocialAccount.objects.filter(user=user).delete()
        logout(request)
        user.delete()

        messages.success(request, '계정이 성공적으로 탈퇴되었습니다.')

        response = redirect('/')
        response.delete_cookie('jwt-auth')
        response.delete_cookie('jwt-refresh')
        response.delete_cookie('sessionid')
        response.delete_cookie('csrftoken')
        return response

    except Exception as e:
        messages.error(request, f'탈퇴 처리 중 오류가 발생했습니다: {str(e)}')
        return redirect('/')


# =========================================================
#  프로필 페이지 + 피드 (내 프로필 / 다른 사람 프로필)
# =========================================================
@login_required
def user_profile(request, nickname=None):
    """
    - /user/profile/           → 내 프로필 (nickname 없음)
    - /user/profile/<nickname>/ → 특정 유저 프로필
    """
    if nickname is None:
        target_user = request.user
    else:
        target_user = get_object_or_404(User, nickname=nickname)

    is_owner = (target_user == request.user)

    # 팔로워 / 팔로잉 숫자 (항상 동일하게 계산)
    follower_count = target_user.follower_set.count()   # Follow.following의 related_name이 'follower_id'인 경우
    following_count = target_user.following_set.count()  # Follow.follower의 related_name이 'following_id'인 경우

    # 내가 이 사람을 팔로우 중인지 여부 (자기 자신일 땐 항상 False)
    is_following = False
    if request.user.is_authenticated and not is_owner:
        is_following = Social.objects.filter(
            follower=request.user,
            following=target_user,
        ).exists()

    posts = (
        Post.objects.filter(writer=target_user)
        .prefetch_related("likes")
        .order_by("-id")
    )

    profile, _ = Profile.objects.get_or_create(user=target_user)

    context = {
        "target_user": target_user,
        "profile": profile,
        "posts": posts,
        "is_owner": is_owner,
        "is_following": is_following,
        "follower_count": follower_count,
        "following_count": following_count,
    }

    return render(request, "user/profile.html", context)

# =========================================================
# fllowers / followings 목록 (AJAX 전용)
@login_required
def followers_list_ajax(request, nickname):
    target = get_object_or_404(User, nickname=nickname)

    # 나를 팔로우하는 사람들
    qs = (
        Social.objects.filter(following=target)
        .select_related("follower")
        .order_by("-created_at")
    )

    users_data = []
    for rel in qs:
        u = rel.follower
        profile = getattr(u, "profile", None)
        img_url = profile.profile_img.url if profile and profile.profile_img else None

        users_data.append(
            {
                "nickname": u.nickname,
                "username": u.username,
                "profile_img": img_url,
            }
        )

    return JsonResponse({"users": users_data})


@login_required
def followings_list_ajax(request, nickname):
    target = get_object_or_404(User, nickname=nickname)

    # 내가 팔로우하는 사람들
    qs = (
        Social.objects.filter(follower=target)
        .select_related("following")
        .order_by("-created_at")
    )

    users_data = []
    for rel in qs:
        u = rel.following
        profile = getattr(u, "profile", None)
        img_url = profile.profile_img.url if profile and profile.profile_img else None

        users_data.append(
            {
                "nickname": u.nickname,
                "username": u.username,
                "profile_img": img_url,
            }
        )

    return JsonResponse({"users": users_data})

# =========================================================
# =========================================================
#  좋아요 토글 (AJAX 전용)
# =========================================================
@login_required
@require_POST
def post_like_toggle_ajax(request, post_id):
    """
    /users/post/<post_id>/like-toggle/ajax/
    - 항상 JSON 응답
    - JS에서 data.is_liked, data.like_count 를 사용
    """
    post = get_object_or_404(Post, id=post_id)

    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        # 이미 좋아요 → 취소
        like.delete()
        is_liked = False
    else:
        is_liked = True

    like_count = post.likes.count()

    return JsonResponse({
        "is_liked": is_liked,      # ✅ JS와 키 이름 맞춤
        "like_count": like_count,
    })


# =========================================================
#  댓글 목록 + 작성 (AJAX 전용)
# =========================================================
@login_required
@require_http_methods(["GET", "POST"])
def post_comments_ajax(request, post_id):
    """
    /users/post/<post_id>/comments/ajax/
    - GET  : 댓글 목록 조회 → {comments: [...]}
    - POST : 댓글 작성      → {success: true, comment: {...}}
    """
    post = get_object_or_404(Post, id=post_id)

    # ---------- GET: 댓글 목록 ----------
    if request.method == "GET":
        comments = (
            Comment.objects
            .filter(post=post)
            .select_related("user")
            .order_by("created_at")
        )

        data = []
        for c in comments:
            data.append({
                "id": c.id,
                "writer_nickname": getattr(c.user, "nickname", c.user.username),
                "content": c.content,
                "created_at": timezone.localtime(c.created_at).strftime("%Y-%m-%d %H:%M"),
            })

        return JsonResponse({"comments": data})

    # ---------- POST: 댓글 작성 ----------
    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    content = (body.get("content") or "").strip()
    if not content:
        return JsonResponse({"success": False, "error": "내용을 입력해주세요."}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        content=content,
    )

    comment_data = {
        "id": comment.id,
        "writer_nickname": getattr(comment.user, "nickname", comment.user.username),
        "content": comment.content,
        "created_at": timezone.localtime(comment.created_at).strftime("%Y-%m-%d %H:%M"),
    }

    return JsonResponse({
        "success": True,
        "comment": comment_data,
    })

# =========================================================
#  팔로우 / 언팔로우 (AJAX 전용)
# =========================================================
@login_required
@require_POST
def follow_toggle_ajax(request, nickname):
    """
    /users/follow/<nickname>/ajax/
    - 항상 JSON 응답
    - JS 에서 data.is_following, data.follower_count 사용
    """
    target_user = get_object_or_404(User, nickname=nickname)

    # 자기 자신은 팔로우 불가
    if target_user == request.user:
        return JsonResponse(
            {"success": False, "error": "본인 계정은 팔로우할 수 없습니다."},
            status=400,
        )

    relation, created = Social.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )

    if not created:
        # 이미 팔로우 → 언팔로우
        relation.delete()
        is_following = False
    else:
        is_following = True

    follower_count = target_user.follower_set.count()

    return JsonResponse({
        "success": True,
        "is_following": is_following,
        "follower_count": follower_count,
    })

# =========================================================

@login_required
def follow_toggle(request, nickname):
    target_user = get_object_or_404(User, nickname=nickname)

    if request.user == target_user:
        return JsonResponse({"error": "본인 계정은 팔로우할 수 없습니다."}, status=400)

    follow, created = Social.objects.get_or_create(
        follower=request.user,
        following=target_user
    )

    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True

    follower_count = target_user.follower_set.count()

    return JsonResponse({
        "is_following": is_following,
        "follower_count": follower_count,
    })


# =========================================================
#  게시글 작성 / 삭제
# =========================================================
@login_required
@require_POST
def post_create(request):
    """
    게시글 작성
    - form에서 name="title", name="content", name="share_trip" 사용
    """
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('share_trip')

    if title or content or image:
        Post.objects.create(
            writer=request.user,
            title=title,
            content=content,
            share_trip=image
        )

    # 작성 후 내 프로필로 이동
    return redirect('users:user_profile')


@login_required
@require_POST
def post_delete(request, post_id):
    """
    게시글 삭제 (본인 게시글만)
    """
    post = get_object_or_404(Post, id=post_id, writer=request.user)
    post.delete()

    # 삭제 후 돌아갈 곳 (현재 페이지)
    return redirect(request.META.get('HTTP_REFERER', 'users:user_profile'))


# =========================================================
#  좋아요 토글
# =========================================================
@login_required
@require_POST
def post_like_toggle(request, post_id):
    """
    좋아요 / 좋아요 취소 토글
    - Ajax 요청이면 JSON 응답
    - 일반 폼이면 프로필로 리다이렉트
    """
    post = get_object_or_404(Post, id=post_id)

    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        # 이미 있던 좋아요면 삭제 = 좋아요 취소
        like.delete()
        liked = False
    else:
        liked = True

    like_count = post.likes.count()

    # Ajax 요청 처리
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': liked, 'like_count': like_count})

    # 일반 요청이면 뒤로
    return redirect(request.META.get('HTTP_REFERER', 'users:user_profile'))


# =========================================================
#  댓글 작성 / 삭제
# =========================================================
@login_required
@require_POST
def comment_create(request, post_id):
    """
    댓글 작성
    - form 에 name="content" 사용
    """
    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '').strip()

    if content:
        Comment.objects.create(
            user=request.user,
            post=post,
            content=content
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # 프론트에서 새로 그리려면 추가 데이터 내려도 됨
        return JsonResponse({
            'success': True,
            'comment_count': post.comments.count(),
        })

    return redirect(request.META.get('HTTP_REFERER', 'users:user_profile'))


@login_required
@require_POST
def comment_delete(request, comment_id):
    """
    댓글 삭제 (작성자 본인만)
    """
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    post = comment.post
    comment.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'comment_count': post.comments.count(),
        })

    return redirect(request.META.get('HTTP_REFERER', 'users:user_profile'))


# =========================================================
#  팔로우 / 언팔로우
# =========================================================
@login_required
@require_POST
def follow_toggle(request, nickname):
    """
    팔로우 / 언팔로우 토글
    - 자기 자신은 팔로우 불가
    """
    target_user = get_object_or_404(User, nickname=nickname)

    if target_user == request.user:
        return redirect(request.META.get('HTTP_REFERER', 'users:user_profile'))

    relation, created = Social.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )

    if not created:
        # 이미 팔로우 중이면 언팔로우
        relation.delete()
        is_following = False
    else:
        is_following = True

    follower_count = target_user.follower_set.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'is_following': is_following,
            'follower_count': follower_count,
        })

    # 팔로우/언팔로우 후 해당 유저 프로필로 이동
    return redirect('users:profile_detail', nickname=nickname)


# =========================================================
#  프로필 이미지 업로드 (기존 코드 유지)
# =========================================================
@login_required
@require_http_methods(["POST"])
def upload_profile_image(request):
    """
    프로필 이미지 업로드 (base64)
    """
    try:
        data = json.loads(request.body)
        image_data = data.get('image')

        if not image_data:
            return JsonResponse({'success': False, 'error': '이미지 데이터가 없습니다.'})

        # data:image/png;base64,... 형식 헤더 제거
        if ',' in image_data:
            format, imgstr = image_data.split(';base64,')
            ext = format.split('/')[-1]
        else:
            return JsonResponse({'success': False, 'error': '잘못된 이미지 형식입니다.'})

        image_file = ContentFile(
            base64.b64decode(imgstr),
            name=f'profile_{uuid.uuid4()}.{ext}'
        )

        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.profile_img:
            profile.profile_img.delete()

        profile.profile_img = image_file
        profile.save()

        return JsonResponse({
            'success': True,
            'image_url': profile.profile_img.url,
            'message': '프로필 이미지가 성공적으로 업데이트되었습니다!'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


from django.db.models import Q

@login_required
def profile_search(request):
    query = request.GET.get("q", "").strip()

    if not query:
        messages.error(request, "검색어를 입력해주세요.")
        return redirect("users:user_profile")

    # 공백 여러 개 → 하나로 정규화
    query_normalized = " ".join(query.split())

    user = (
        User.objects
        .filter(
            Q(nickname__iexact=query_normalized) |
            Q(email__iexact=query_normalized)
        )
        .first()
    )

    if not user:
        messages.error(request, "해당 닉네임/이메일의 사용자를 찾을 수 없습니다.")
        return redirect("users:user_profile")

    return redirect("users:profile_detail", nickname=user.nickname)


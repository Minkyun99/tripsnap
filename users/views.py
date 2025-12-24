from __future__ import annotations

import base64
import json
import random
import uuid
import traceback
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q

from allauth.socialaccount.models import SocialAccount

from .forms import CustomUserCreationForm
from .models import Profile, Post, PostImage, Like, Comment, Social
from chatbot.models import Bakery
from .serializers import PostSerializer

from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


# =========================================================
# Helpers
# =========================================================
def is_ajax(request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def abs_url(request, url_or_none):
    """
    Django FileField.url(/media/...) -> http://localhost:8000/media/... 로 변환
    """
    if not url_or_none:
        return None
    return request.build_absolute_uri(url_or_none)


def generate_unique_nickname() -> str:
    adjectives = [
        "따뜻한", "뜨거운", "갓 구운", "신선한", "폭신한", "보송보송한",
        "쫄깃한", "바삭한", "파삭한", "부드러운", "촉촉한", "퍽퍽한",
        "거친", "묵직한", "고소한", "달콤한", "담백한", "짭짤한",
        "신맛이 나는", "시큼한", "풍부한", "향긋한", "노릇노릇한",
        "탐스러운", "먹음직스러운", "마른", "딱딱한", "매끈한", "겉바속촉", "눅눅한", "푸석푸석한", "미끌미끌한"
    ]
    nouns = [
        "밀가루", "효모", "이스트", "버터", "우유", "설탕", "소금", "계란",
        "반죽", "오븐", "베이커리", "빵집", "제빵사", "식빵", "바게트",
        "크루아상", "베이글", "모닝빵", "도넛", "케이크", "사워도우",
        "깜빠뉴", "크러스트", "겉껍질", "속살", "빵조각", "기포", "트레이", "피자빵", "맘모스", "뚱카롱", "식빵", "김치찹쌀주먹밥", "튀소"
    ]

    while True:
        nickname = f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 999)}"
        if not User.objects.filter(nickname=nickname).exists():
            return nickname


def _can_view_follow_list(viewer: User, owner: User) -> bool:
    """
    owner의 팔로워/팔로잉 목록을 viewer가 볼 수 있는지 판단.

    follow_visibility:
      - public: 누구나(로그인 사용자) 조회 가능
      - following_only: owner가 팔로우한 사용자에게만 공개 (owner -> viewer 관계가 있어야 함)
      - private: 본인만
    """
    if not viewer.is_authenticated:
        return False

    visibility = getattr(owner, "follow_visibility", "public") or "public"

    if visibility == "public":
        return True

    if visibility == "private":
        return viewer == owner

    # following_only
    return (viewer == owner) or Social.objects.filter(follower=owner, following=viewer).exists()


@require_GET
def current_user_or_guest(request):
    """
    로그인되어 있으면 사용자 정보 + is_authenticated=True
    비로그인이어도 200 OK + is_authenticated=False 를 내려주는 엔드포인트
    """
    if request.user.is_authenticated:
        u = request.user
        data = {
            "is_authenticated": True,
            "user": {
                "id": u.id,
                "email": u.email,
                "username": getattr(u, "username", "") or "",
                "nickname": getattr(u, "nickname", "") or "",
            },
        }
    else:
        data = {
            "is_authenticated": False,
            "user": None,
        }

    return JsonResponse(data)


def _profile_payload(request, target_user: User):
    profile, _ = Profile.objects.get_or_create(user=target_user)

    is_owner = request.user == target_user

    follower_count = target_user.follower_set.count()
    following_count = target_user.following_set.count()

    is_following = False
    if request.user.is_authenticated and not is_owner:
        is_following = Social.objects.filter(follower=request.user, following=target_user).exists()

    posts_qs = (
        Post.objects.filter(writer=target_user)
        .prefetch_related("likes", "images") # "images"는 PostImage의 related_name
        .order_by("-id")
    )


    liked_post_ids = []
    if request.user.is_authenticated:
        liked_post_ids = list(request.user.likes.values_list("post_id", flat=True))

    posts = []
    for p in posts_qs:
        posts.append({
            "id": p.id,
            "title": p.title or "",
            "content": p.content or "",
            "image": abs_url(request, p.share_trip.url) if p.share_trip else "",
            "writer_username": p.writer.username or "",
            "writer_nickname": p.writer.nickname or "",
            "like_count": p.likes.count(),
            "is_liked": (p.id in liked_post_ids),
            "is_owner": (request.user == p.writer),
        })


    serializer = PostSerializer(posts_qs, many=True, context={'request': request})
    
    # 3. Serializer 데이터에 is_owner 정보 추가 (기존 프론트엔드 호환용)
    posts_data = serializer.data
    for p_data in posts_data:
        p_data['is_owner'] = is_owner
        

    payload = {
        "profile": {
            "email": target_user.email or "",
            "nickname": target_user.nickname or "",
            "username": target_user.username or "",
            "profile_img": abs_url(request, profile.profile_img.url) if profile.profile_img else "",
            "follower_count": follower_count,
            "following_count": following_count,
            "follow_visibility": getattr(target_user, "follow_visibility", "public") or "public",
            "is_owner": is_owner,
            "is_following": is_following,
        },
        "posts": posts_data,
    }
    return JsonResponse(payload)


# =========================================================
# CSRF
# =========================================================
@ensure_csrf_cookie
def csrf_cookie(request):
    # Vue SPA에서 최초 1회 호출해서 csrftoken 세팅용
    return JsonResponse({"detail": "CSRF cookie set"})


# =========================================================
# Settings (Template)
# =========================================================
@login_required
def settings_view(request):
    """
    설정 페이지(템플릿): 비밀번호 변경 + 회원 탈퇴(템플릿 버튼)
    """
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "비밀번호가 성공적으로 변경되었습니다.")
            return redirect("users:settings")
        messages.error(request, "입력하신 내용을 다시 확인해주세요.")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "user/setting.html", {"form": form})


# =========================================================
# Signup / Delete (Template)
# =========================================================
def signup(request):
    """
    템플릿 기반 signup (Vue/dj-rest-auth 회원가입과 별개로 유지)
    """
    if request.user.is_authenticated:
        return redirect("users:user_profile")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            if not user.username:
                user.username = (user.email.split("@")[0] if user.email else "user")

            if not user.nickname or not user.nickname.strip():
                user.nickname = generate_unique_nickname()

            user.save()
            return redirect("users:user_profile")
    else:
        form = CustomUserCreationForm()

    return render(request, "account/signup.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def account_delete(request):
    """
    템플릿/폼 기반 탈퇴 (리다이렉트)
    """
    user = request.user
    try:
        SocialAccount.objects.filter(user=user).delete()
        logout(request)
        user.delete()

        messages.success(request, "계정이 성공적으로 탈퇴되었습니다.")
        response = redirect("/")
        response.delete_cookie("jwt-auth")
        response.delete_cookie("jwt-refresh")
        response.delete_cookie("sessionid")
        response.delete_cookie("csrftoken")
        return response
    except Exception as e:
        messages.error(request, f"탈퇴 처리 중 오류가 발생했습니다: {str(e)}")
        return redirect("/")


# =========================================================
# Vue JSON APIs
# =========================================================
@login_required
def profile_me_api(request):
    """
    GET /users/api/profile/me/
    """
    return _profile_payload(request, request.user)


@login_required
def profile_detail_api(request, nickname):
    """
    GET /users/api/profile/<nickname>/
    """
    target = get_object_or_404(User, nickname=nickname)
    return _profile_payload(request, target)


@login_required
@require_http_methods(["GET", "POST"])
def follow_visibility_setting_api(request):
    """
    GET  /users/api/settings/follow-visibility/ -> {"follow_visibility": "..."}
    POST /users/api/settings/follow-visibility/ -> {"follow_visibility": "..."} 저장

    값: public | following_only | private
    """
    if request.method == "GET":
        return JsonResponse({"follow_visibility": getattr(request.user, "follow_visibility", "public") or "public"})

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"detail": "잘못된 요청입니다."}, status=400)

    val = data.get("follow_visibility")
    allowed = {"public", "following_only", "private"}
    if val not in allowed:
        return JsonResponse({"detail": "follow_visibility 값이 올바르지 않습니다."}, status=400)

    request.user.follow_visibility = val
    request.user.save(update_fields=["follow_visibility"])
    return JsonResponse({"follow_visibility": val})


@login_required
def profile_search(request):
    """
    GET /users/api/profile/search/?q=...
    - email 또는 nickname으로 사용자 찾기
    - 성공: {"nickname": "..."}
    - 실패: 404 {"detail": "..."}
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"detail": "검색어가 비어있습니다."}, status=400)

    user = User.objects.filter(email__iexact=q).first()
    if not user:
        user = User.objects.filter(nickname__iexact=q).first()

    if not user:
        return JsonResponse({"detail": "사용자를 찾을 수 없습니다."}, status=404)

    return JsonResponse({"nickname": user.nickname})


# =========================================================
# Profile pages (Template + AJAX fallback)
# =========================================================
@login_required
def user_profile(request, nickname=None):
    """
    GET /users/profile/                -> 내 프로필(템플릿 or AJAX)
    GET /users/profile/<nickname>/     -> 다른 사람 프로필(템플릿 or AJAX)

    - Vue에서는 보통 /users/api/profile/... 를 쓰는 것을 권장하지만,
      기존 템플릿/혼합 구조 호환을 위해 AJAX 요청이면 JSON도 내려줍니다.
    """
    if nickname is None:
        target_user = request.user
    else:
        target_user = get_object_or_404(User, nickname=nickname)

    is_owner = (target_user == request.user)

    follower_count = target_user.follower_set.count()
    following_count = target_user.following_set.count()

    is_following = False
    if request.user.is_authenticated and not is_owner:
        is_following = Social.objects.filter(follower=request.user, following=target_user).exists()

    posts = (
        Post.objects.filter(writer=target_user)
        .prefetch_related("likes")
        .order_by("-id")
    )

    profile, _ = Profile.objects.get_or_create(user=target_user)

    liked_post_ids = []
    if request.user.is_authenticated:
        liked_post_ids = list(request.user.likes.values_list("post_id", flat=True))

    if is_ajax(request):
        posts_data = []
        for p in posts:
            posts_data.append({
                "id": p.id,
                "title": p.title,
                "content": p.content,
                "share_trip": abs_url(request, p.share_trip.url) if p.share_trip else None,
                "like_count": p.likes.count(),
                "comment_count": p.comments.count(),
                "writer_nickname": p.writer.nickname,
                "is_owner": (p.writer_id == request.user.id),
            })


        return JsonResponse({
            "target_user": {
                "email": target_user.email,
                "username": target_user.username,
                "nickname": target_user.nickname,
            },
            "profile": {
                "profile_img": abs_url(request, profile.profile_img.url) if profile.profile_img else None,
            },
            "posts": posts_data,
            "is_owner": is_owner,
            "is_following": is_following,
            "follower_count": follower_count,
            "following_count": following_count,
            "follow_visibility": getattr(target_user, "follow_visibility", "public") or "public",
            "liked_post_ids": liked_post_ids,
        })

    context = {
        "target_user": target_user,
        "profile": profile,
        "posts": posts,
        "is_owner": is_owner,
        "is_following": is_following,
        "follower_count": follower_count,
        "following_count": following_count,
        "follow_visibility": getattr(target_user, "follow_visibility", "public") or "public",
        "liked_post_ids": liked_post_ids,
    }
    return render(request, "user/profile.html", context)


# =========================================================
# Follow toggle (normal + ajax)
# =========================================================
@login_required
@require_http_methods(["POST"])
def follow_toggle(request, nickname):
    """
    POST /users/follow/<nickname>/
    (필요 시 유지: 일반용)
    """
    target_user = get_object_or_404(User, nickname=nickname)
    me = request.user

    if me == target_user:
        return JsonResponse({"detail": "본인 계정은 팔로우할 수 없습니다."}, status=400)

    rel = Social.objects.filter(follower=me, following=target_user).first()
    if rel:
        rel.delete()
        is_following = False
    else:
        Social.objects.create(follower=me, following=target_user)
        is_following = True

    follower_count = target_user.follower_set.count()
    return JsonResponse({"is_following": is_following, "follower_count": follower_count})


@login_required
@require_POST
def follow_toggle_ajax(request, nickname):
    """
    POST /users/follow/<nickname>/ajax/
    - JS에서 쓰는 URL
    """
    target_user = get_object_or_404(User, nickname=nickname)
    me = request.user

    if me == target_user:
        return JsonResponse({"success": False, "error": "본인 계정은 팔로우할 수 없습니다."}, status=400)

    relation, created = Social.objects.get_or_create(follower=me, following=target_user)
    if not created:
        relation.delete()
        is_following = False
    else:
        is_following = True

    follower_count = target_user.follower_set.count()
    return JsonResponse({"success": True, "is_following": is_following, "follower_count": follower_count})


# =========================================================
# Follow lists (Modal)
# =========================================================
@login_required
def followers_list_ajax(request, nickname):
    """
    GET /users/profile/<nickname>/followers/ajax/
    """
    target = get_object_or_404(User, nickname=nickname)

    if not _can_view_follow_list(request.user, target):
        # 403 대신 200 + private 플래그 (브라우저 콘솔/서버 로그의 403 spam 방지)
        return JsonResponse({"users": [], "private": True, "detail": "비공개 입니다."})

    qs = (
        Social.objects.filter(following=target)
        .select_related("follower")
        .order_by("-created_at")
    )

    users_data = []
    for rel in qs:
        u = rel.follower
        profile = getattr(u, "profile", None)
        img_url = abs_url(request, profile.profile_img.url) if profile and getattr(profile, "profile_img", None) else None
        users_data.append({"nickname": u.nickname, "username": u.username, "profile_img": img_url})

    return JsonResponse({"users": users_data, "private": False})


@login_required
def followings_list_ajax(request, nickname):
    """
    GET /users/profile/<nickname>/followings/ajax/
    """
    target = get_object_or_404(User, nickname=nickname)

    if not _can_view_follow_list(request.user, target):
        return JsonResponse({"users": [], "private": True, "detail": "비공개 입니다."})

    qs = (
        Social.objects.filter(follower=target)
        .select_related("following")
        .order_by("-created_at")
    )

    users_data = []
    for rel in qs:
        u = rel.following
        profile = getattr(u, "profile", None)
        img_url = abs_url(request, profile.profile_img.url) if profile and getattr(profile, "profile_img", None) else None
        users_data.append({"nickname": u.nickname, "username": u.username, "profile_img": img_url})

    return JsonResponse({"users": users_data, "private": False})


# =========================================================
# Profile image upload (base64)
# =========================================================
@login_required
@require_http_methods(["POST"])
def upload_profile_image(request):
    """
    POST /users/upload-profile-image/
    { "image": "data:image/png;base64,...." }
    """
    try:
        data = json.loads(request.body or "{}")
        image_data = data.get("image")

        if not image_data:
            return JsonResponse({"success": False, "error": "이미지 데이터가 없습니다."}, status=400)

        if "," not in image_data or ";base64," not in image_data:
            return JsonResponse({"success": False, "error": "잘못된 이미지 형식입니다."}, status=400)

        fmt, imgstr = image_data.split(";base64,")
        ext = fmt.split("/")[-1]

        image_file = ContentFile(
            base64.b64decode(imgstr),
            name=f"profile_{uuid.uuid4()}.{ext}",
        )

        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.profile_img:
            profile.profile_img.delete(save=False)

        profile.profile_img = image_file
        profile.save()

        return JsonResponse({
            "success": True,
            "image_url": abs_url(request, profile.profile_img.url),
            "message": "프로필 이미지가 성공적으로 업데이트되었습니다!",
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# =========================================================
# Posts
# =========================================================
@login_required
@require_POST
def post_create(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    images_base64 = body.get("images") or []

    if not title or not content:
        return JsonResponse({"error": "제목과 내용을 모두 입력해주세요."}, status=400)

    try:
        # 1. 게시물 본문 생성
        post = Post.objects.create(
            writer=request.user,
            title=title,
            content=content,
        )

        # 2. 이미지 배열 처리
        for idx, base64_str in enumerate(images_base64):
            if not base64_str or ";base64," not in base64_str:
                continue

            header, encoded = base64_str.split(";base64,")
            ext = header.split("/")[-1]
            
            image_file = ContentFile(
                base64.b64decode(encoded),
                name=f'post_{post.id}_{idx}_{uuid.uuid4()}.{ext}'
            )

            # 첫 번째 사진을 대표 이미지(share_trip)로 저장
            if idx == 0:
                post.share_trip = image_file
                post.save()

            # 모든 사진을 PostImage 모델에 개별 레코드로 저장
            PostImage.objects.create(
                post=post,
                image=image_file
            )

        serializer = PostSerializer(post, context={'request': request})
        
        return JsonResponse({
            "message": "게시글이 성공적으로 작성되었습니다.",
            "post": serializer.data
        })

    except Exception as e:
        return JsonResponse({"error": f"서버 오류: {str(e)}"}, status=500)

@login_required
@require_POST
def post_update_ajax(request, post_id):
    """
    POST /users/post/<post_id>/update/ajax/
    JSON: {title, content}
    """
    post = get_object_or_404(Post, id=post_id, writer=request.user)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()

    if not title:
        return JsonResponse({"success": False, "error": "제목을 입력하세요."}, status=400)

    post.title = title
    post.content = content
    post.save(update_fields=["title", "content"])

    return JsonResponse({"success": True, "post": {"id": post.id, "title": post.title, "content": post.content}})


@login_required
@require_http_methods(["POST"])
def post_delete(request, post_id):
    """
    POST /users/post/<post_id>/delete/
    """
    post = get_object_or_404(Post, id=post_id, writer=request.user)
    post.delete()

    if is_ajax(request):
        return JsonResponse({"success": True, "id": post_id})

    return redirect(request.META.get("HTTP_REFERER", "users:user_profile"))


# =========================================================
# Likes
# =========================================================
@login_required
@require_POST
def post_like_toggle(request, post_id):
    """
    POST /users/post/<post_id>/like-toggle/
    (일반용)
    """
    post = get_object_or_404(Post, id=post_id)

    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    like_count = post.likes.count()

    if is_ajax(request):
        return JsonResponse({"liked": liked, "like_count": like_count})

    return redirect(request.META.get("HTTP_REFERER", "users:user_profile"))


@login_required
@require_POST
def post_like_toggle_ajax(request, post_id):
    """
    POST /users/post/<post_id>/like-toggle/ajax/
    """
    post = get_object_or_404(Post, id=post_id)

    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
        is_liked = False
    else:
        is_liked = True

    like_count = post.likes.count()
    return JsonResponse({"is_liked": is_liked, "like_count": like_count})


# =========================================================
# Comments
# =========================================================
@login_required
@require_POST
def comment_create(request, post_id):
    """
    POST /users/post/<post_id>/comment/
    form-data: content
    """
    post = get_object_or_404(Post, id=post_id)
    content = (request.POST.get("content") or "").strip()

    if not content:
        return JsonResponse({"success": False, "error": "내용을 입력하세요."}, status=400) if is_ajax(request) else redirect(request.META.get("HTTP_REFERER", "users:user_profile"))

    Comment.objects.create(user=request.user, post=post, content=content)

    if is_ajax(request):
        return JsonResponse({"success": True, "comment_count": post.comments.count()})

    return redirect(request.META.get("HTTP_REFERER", "users:user_profile"))


@login_required
@require_http_methods(["GET", "POST"])
def post_comments_ajax(request, post_id):
    """
    GET/POST /users/post/<post_id>/comments/ajax/
    """
    post = get_object_or_404(Post, id=post_id)

    if request.method == "GET":
        comments = post.comments.select_related("user").order_by("created_at")
        return JsonResponse({
            "comments": [
                {
                    "id": c.id,
                    "writer_nickname": c.user.nickname,
                    "content": c.content,
                    "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
                    "is_owner": (request.user == c.user),
                }
                for c in comments
            ]
        })

    # POST
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    content = (body.get("content") or "").strip()
    if not content:
        return JsonResponse({"success": False, "error": "내용을 입력하세요."}, status=400)

    comment = Comment.objects.create(post=post, user=request.user, content=content)
    return JsonResponse({
        "success": True,
        "comment": {
            "id": comment.id,
            "writer_nickname": comment.user.nickname,
            "content": comment.content,
            "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_owner": True,
        }
    })


@login_required
@require_http_methods(["POST"])
def comment_update_ajax(request, comment_id):
    """
    POST /users/comment/<comment_id>/edit/ajax/
    JSON: {content}
    """
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    new_content = (body.get("content") or "").strip()
    if not new_content:
        return JsonResponse({"success": False, "error": "내용을 입력하세요."}, status=400)

    comment.content = new_content
    comment.save(update_fields=["content", "updated_at"])

    return JsonResponse({
        "success": True,
        "id": comment.id,
        "content": comment.content,
        "updated_at": comment.updated_at.strftime("%Y-%m-%d %H:%M"),
    })


@login_required
@require_POST
def comment_delete_ajax(request, comment_id):
    """
    POST /users/comment/<comment_id>/delete/ajax/
    """
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    comment.delete()
    return JsonResponse({"success": True, "id": comment_id})


# =========================================================
# Account delete API (Vue JSON)
# =========================================================
@login_required
@require_POST
def account_delete_api(request):
    """
    POST /users/api/account/delete/
    - 성공: {success: true}
    """
    user = request.user
    try:
        SocialAccount.objects.filter(user=user).delete()
        logout(request)
        user.delete()

        res = JsonResponse({"success": True})
        res.delete_cookie("jwt-auth")
        res.delete_cookie("jwt-refresh")
        res.delete_cookie("sessionid")
        res.delete_cookie("csrftoken")
        return res
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    

@login_required
def recommended_bakeries_api(request):
    """
    GET /users/api/recommended-bakeries/

    - 사용자(User)의 keywords 기반으로 Bakery 추천
    - 사용자 키워드가 없으면 → 추천 안 함 (빈 리스트)
    - 키워드는 있으나 매칭되는 빵집이 없으면 → 빈 리스트
    """

    user = request.user

    # -----------------------------
    # 1. 사용자 키워드 정규화
    # -----------------------------
    raw = getattr(user, "keywords", None)

    user_keywords: list[str] = []

    if isinstance(raw, str):
        base = raw.strip()
        if base:
            base = base.replace(";", ",")
            user_keywords = [k.strip() for k in base.split(",") if k.strip()]

    elif isinstance(raw, (list, tuple, set)):
        user_keywords = [str(k).strip() for k in raw if str(k).strip()]

    elif isinstance(raw, dict):
        if "keywords" in raw and isinstance(raw["keywords"], (list, tuple, set)):
            user_keywords = [str(k).strip() for k in raw["keywords"] if str(k).strip()]
        else:
            user_keywords = [str(k).strip() for k in raw.keys() if str(k).strip()]

    user_kw_set = {k for k in user_keywords if k}

    # -----------------------------
    # 2. 키워드 없으면 → 바로 빈 리스트 반환
    # -----------------------------
    if not user_kw_set:
        return JsonResponse({"results": []})

    # -----------------------------
    # 3. Bakery 쿼리셋 준비
    # -----------------------------
    qs = Bakery.objects.all()

    # -----------------------------
    # 4. 키워드 매칭 스코어링
    # -----------------------------
    scored: list[tuple[int, Bakery]] = []

    for bakery in qs.only(
        "id",
        "name",
        "district",
        "road_address",
        "jibun_address",
        "url",
        "keywords",
    )[:500]:
        b_raw = bakery.keywords or ""

        if isinstance(b_raw, str):
            b_keywords = {w.strip() for w in b_raw.replace(";", ",").split(",") if w.strip()}
        elif isinstance(b_raw, (list, tuple, set)):
            b_keywords = {str(w).strip() for w in b_raw if str(w).strip()}
        else:
            b_keywords = set()

        common = user_kw_set & b_keywords
        score = len(common)

        if score > 0:
            scored.append((score, bakery))

    # -----------------------------
    # 5. 매칭 결과 없으면 → 빈 리스트
    # -----------------------------
    if not scored:
        return JsonResponse({"results": []})

    # 점수 내림차순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)

    # 상위 50개 중 랜덤 최대 6개
    top_candidates = [b for _, b in scored[:50]]
    if len(top_candidates) <= 6:
        selected = top_candidates
    else:
        selected = random.sample(top_candidates, 6)

    # -----------------------------
    # 6. 응답 JSON 생성
    # -----------------------------
    results = []
    for b in selected:
        b_kw_raw = b.keywords or ""
        if isinstance(b_kw_raw, str):
            kw_list = [w.strip() for w in b_kw_raw.replace(";", ",").split(",") if w.strip()]
        elif isinstance(b_kw_raw, (list, tuple, set)):
            kw_list = [str(w).strip() for w in b_kw_raw if str(w).strip()]
        else:
            kw_list = []

        results.append(
            {
                "id": b.id,
                "name": b.name,
                "district": b.district,
                "road_address": b.road_address,
                "jibun_address": b.jibun_address,
                "url": b.url,
                "keywords": kw_list,
                "rate" : b.rate
            }
        )

    return JsonResponse({"results": results})


@login_required
@require_http_methods(["POST"])
def build_user_keywords_api(request):
    """
    POST /users/api/settings/build-user-keywords/
    관리자(tripsnap@tripsnap.com)만 호출 가능.
    """
    # ✅ 관리자 체크
    if request.user.email != "tripsnap@tripsnap.com":
        return JsonResponse(
            {"success": False, "detail": "권한이 없습니다."},
            status=403,
        )

    # ✅ (선택) limit 옵션을 JSON body 로 받을 수 있게 처리
    limit = None
    try:
      if request.body:
          payload = json.loads(request.body.decode("utf-8"))
          limit = payload.get("limit")
    except Exception:
        # body 파싱 실패해도 limit 없이 그냥 진행
        pass

    try:
        cmd_kwargs = {}
        if limit is not None:
            cmd_kwargs["limit"] = int(limit)

        # 🔥 여기서 management command 실행
        call_command("build_user_keywords", **cmd_kwargs)

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("build_user_keywords command failed: %s\n%s", e, tb)

        # ✅ 프론트에서 디버깅할 수 있도록 에러 메시지와 트레이스백을 내려줌
        return JsonResponse(
            {
                "success": False,
                "detail": f"키워드 추출 중 오류가 발생했습니다: {e}",
                "traceback": tb,
            },
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "detail": "사용자 키워드 추출 작업이 정상적으로 실행되었습니다.",
            "ran_at": timezone.now().isoformat(),
        }
    )
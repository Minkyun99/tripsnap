from __future__ import annotations

import base64
import json
import random
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods

from allauth.socialaccount.models import SocialAccount

from .forms import CustomUserCreationForm
from .models import Profile, Post, Like, Comment, Social

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
        "탐스러운", "먹음직스러운", "마른", "딱딱한", "매끈한", "겉바속촉", "눅눅한"
    ]
    nouns = [
        "밀가루", "효모", "이스트", "버터", "우유", "설탕", "소금", "계란",
        "반죽", "오븐", "베이커리", "빵집", "제빵사", "식빵", "바게트",
        "크루아상", "베이글", "모닝빵", "도넛", "케이크", "사워도우",
        "깜빠뉴", "크러스트", "겉껍질", "속살", "빵조각", "기포", "트레이"
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
        .prefetch_related("likes")
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
        "posts": posts,
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
    image_base64 = body.get("image_base64")

    image_file = None
    if image_base64:
        try:
            header, encoded = image_base64.split(";base64,")
            ext = header.split("/")[-1]
            image_file = ContentFile(
                base64.b64decode(encoded),
                name=f'post_{uuid.uuid4()}.{ext}'
            )
        except Exception:
            return JsonResponse({"error": "이미지 처리 실패"}, status=400)

    post = Post.objects.create(
        writer=request.user,
        title=title,
        content=content,
        share_trip=image_file,
    )

    return JsonResponse({
        "post": {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "image": abs_url(request, post.share_trip.url) if post.share_trip else None,
            "like_count": 0,
            "is_liked": False,
        }
    })


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

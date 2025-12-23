# users/management/commands/build_user_keywords.py

import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from users.models import Post

from . import model_ver11  # 같은 폴더의 model_ver11.py 사용

User = get_user_model()


class Command(BaseCommand):
    help = "모든 사용자의 게시글을 기반으로 키워드를 추출하여 User.keywords 필드에 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="테스트용: 앞에서부터 N명의 사용자만 처리",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")
        # 1) model_ver11.py가 있는 디렉터리 기준으로 경로 잡기

        model_dir = os.path.dirname(model_ver11.__file__)

        base_kw_path = os.path.join(model_dir, model_ver11.BASE_KEYWORD_PATH)
        new_kw_path = os.path.join(model_dir, model_ver11.NEW_KEYWORD_PATH)
        dessert_meta_path = os.path.join(model_dir, model_ver11.DESSERT_META_PATH)

        # 2) base_keywords.json 존재 여부 체크
        if not os.path.exists(base_kw_path):
            self.stderr.write(self.style.ERROR(f"base_keywords.json 없음: {base_kw_path}"))
            return


        if not os.path.exists(new_kw_path):
            self.stdout.write(self.style.WARNING(f"new_keyword.json 없음(무시하고 진행): {new_kw_path}"))
        if not os.path.exists(dessert_meta_path):
            self.stdout.write(
                self.style.WARNING(f"dessert_en.json 없음(매장 메타 없이 진행): {dessert_meta_path}")
            )
        self.stdout.write(self.style.WARNING(f"키워드 설정 로드: {base_kw_path} / {new_kw_path}"))

        # 3) 키워드 설정 로드
        kw_by_cat, label_list, label2id, id2label, kw2cat = model_ver11.load_keyword_config(
            base_path=base_kw_path,
            new_path=new_kw_path,
        )

        # (선택) 매장 메타 – 사용자 텍스트에서는 크게 의미 없지만, 구조상 로드
        _place_profiles = model_ver11.load_dessert_profiles(dessert_meta_path)

        # 4) 학습된 키워드 추출 모델 로드
        self.stdout.write(self.style.WARNING("학습된 KoELECTRA 키워드 모델 로드 중..."))
        model, tokenizer, _label_list_from_ckpt, _kw2cat_from_ckpt = (
            model_ver11.load_trained_model_for_inference()
        )

        # ckpt 기준 label_list / kw2cat 사용
        label_list = _label_list_from_ckpt
        kw2cat = _kw2cat_from_ckpt

        # 5) 사용자 루프를 돌면서 게시글 내용 수집 → 키워드 추출
        qs = User.objects.all().order_by("id")
        if limit:
            qs = qs[:limit]

        total_users = qs.count()
        self.stdout.write(self.style.SUCCESS(f"총 {total_users}명 사용자 키워드 추출 시작"))

        for idx, user in enumerate(qs, start=1):
            # 해당 사용자의 게시글 내용 모으기
            posts = Post.objects.filter(writer=user).order_by("created_at")
            texts = [(p.content or "").strip() for p in posts if (p.content or "").strip()]

            if not texts:
                # 게시글이 없으면 빈 리스트로 저장
                user.keywords = []
                user.save(update_fields=["keywords"])
                self.stdout.write(f"[{idx}/{total_users}] {user} - 게시글 없음 → keywords=[]")
                continue

            # model_ver11 의 추론 함수 사용
            result = model_ver11.predict_keywords_for_texts(
                texts=texts,
                model=model,
                tokenizer=tokenizer,
                label_list=label_list,
                kw_by_cat=kw_by_cat,
                kw2cat=kw2cat,
                place_profile=None,  # 사용자 텍스트라서 별도 place_profile 은 사용하지 않음
            )

            final_keywords = result.get("final_keywords", [])

            user.keywords = final_keywords
            user.save(update_fields=["keywords"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"[{idx}/{total_users}] {user} - 추출 키워드 {len(final_keywords)}개 저장"
                )
            )

        self.stdout.write(self.style.SUCCESS("✅ 모든 사용자 키워드 추출 및 저장 완료"))

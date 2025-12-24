# model_ver11.py

# ------------------------------------------------------------
# KoELECTRA 멀티라벨 키워드 추출 모델 (빵집/카페 리뷰용)
# - ver10 개선 + 부정 문맥(하지 않다/없다 등) 처리 강화
# - 키워드별 "양성 등장(review 비율/회수)"까지 산출해 JSON에 저장
# - 과도한 최소 등장 횟수 필터 대신, 빈도/비율은 나중 랭킹 단계에서 활용
# ------------------------------------------------------------

import os
import re
import json
import math
import random
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
import torch.nn.functional as F

from transformers import AutoTokenizer, AutoModel

# ============================================================
# 0. 기본 설정
# ============================================================

BASE_MODEL_NAME = "monologg/koelectra-base-v3-discriminator"

# 이 값들은 "파일 이름"만 정의합니다. 실제 경로는 사용할 때 조합합니다.
BASE_KEYWORD_PATH = "base_keywords.json"
NEW_KEYWORD_PATH = "new_keyword.json"
TRAIN_DIR = "train_ver2"  # 학습 시에만 사용
CHECKPOINT_PATH = "best_koelectra_model_ver11.pth"  # ★ ver11 저장 이름

DESSERT_META_PATH = "dessert_en.json"

MAX_SEQ_LEN = 256
BATCH_SIZE = 16
EPOCHS = 3
K_FOLD = 1  # 1이면 train/val 8:2, 이후 full train

BASE_LR = 3e-5
HEAD_LR = 1e-4

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"DEVICE: {DEVICE}")


def normalize_text_basic(text: str) -> str:
    return text.replace(" ", "").lower()


# ============================================================
# 1. 시드 & JSON 유틸
# ============================================================

def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 2. 키워드 설정
# ============================================================

def load_keyword_config(
    base_path: str = BASE_KEYWORD_PATH,
    new_path: str = NEW_KEYWORD_PATH,
) -> Tuple[Dict[str, List[str]], List[str], Dict[str, int], Dict[int, str], Dict[str, str]]:
    """
    base_keywords.json + new_keyword.json 을 합쳐 최종 라벨 리스트와
    카테고리 맵(kw2cat)을 만든다.
    """
    base_cfg = load_json(base_path)
    categories = ["menu", "taste", "texture", "topping", "store"]

    kw_by_cat: Dict[str, List[str]] = {}
    for cat in categories:
        kw_by_cat[cat] = base_cfg.get(cat, [])

    base_all_raw = base_cfg.get("all_keywords", [])
    base_all = sorted(list(set(base_all_raw)))

    # new_keyword.json 이 있으면 추가 키워드 로드
    if os.path.exists(new_path):
        new_cfg = load_json(new_path)
        new_all_raw = new_cfg.get("all_keywords", [])
    else:
        new_all_raw = []

    new_only = [k for k in new_all_raw if k not in base_all]
    all_keywords = base_all + new_only

    label2id = {kw: i for i, kw in enumerate(all_keywords)}
    id2label = {i: kw for kw, i in label2id.items()}

    # kw2cat: 각 키워드 → 카테고리
    kw2cat: Dict[str, str] = {}
    for cat, kws in kw_by_cat.items():
        for k in kws:
            kw2cat[k] = cat

    # new_only 중 카테고리 지정 안 된 것은 일단 menu 로
    for k in new_only:
        if k not in kw2cat:
            kw2cat[k] = "menu"

    print("------------------------------------------------------------")
    print("📋 키워드 설정 요약")
    print(f"  - base_all_raw 개수 (중복 포함): {len(base_all_raw)}")
    print(f"  - base_all 개수 (중복 제거): {len(base_all)}")
    print(f"  - new_keywords_raw 개수: {len(new_all_raw)}")
    print(f"  - new_only 개수: {len(new_only)}")
    print(f"  - 최종 라벨 개수: {len(all_keywords)}")
    print("------------------------------------------------------------")

    return kw_by_cat, all_keywords, label2id, id2label, kw2cat


# ============================================================
# 3. dessert_en 기반 매장 메타 (음료/빵 비율만 사용)
# ============================================================

BEVERAGE_TOKENS = [
    "커피", "아메리카노", "라떼", "라테", "콜드브루",
    "카푸치노", "에스프레소", "음료", "차", "티",
    "에이드", "스무디", "주스"
]

DESSERT_TOKENS = [
    "빵", "디저트", "케이크", "베이커리",
    "크로와상", "크루아상", "스콘", "쿠키", "타르트",
    "마카롱", "마들렌", "휘낭시에", "까눌레", "도넛", "도너츠",
    "크로플", "브라우니", "파이", "롤케이크", "샌드위치"
]


def build_place_profile_from_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    dessert_en.json 안의 review_keywords 기반으로
    '음료 위주 카페'인지 대략 판별.
    """
    review_keywords = meta.get("review_keywords", [])

    beverage_score = 0
    dessert_score = 0

    for item in review_keywords:
        kw_text = item.get("keyword", "")
        cnt = item.get("count", 0)
        if any(tok in kw_text for tok in BEVERAGE_TOKENS):
            beverage_score += cnt
        if any(tok in kw_text for tok in DESSERT_TOKENS):
            dessert_score += cnt

    menu_keywords = set()

    is_beverage_shop = False
    if beverage_score >= 20 and beverage_score >= 2 * max(dessert_score, 1):
        is_beverage_shop = True

    return {
        "is_beverage_shop": is_beverage_shop,
        "menu_keywords": menu_keywords,
        "beverage_score": beverage_score,
        "dessert_score": dessert_score,
    }


def load_dessert_profiles(path: str = DESSERT_META_PATH) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        print(f"⚠️ dessert_en.json 없음: {path} (매장 메타 없이 진행)")
        return {}

    raw = load_json(path)
    profiles: Dict[str, Dict[str, Any]] = {}

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = list(raw.values())
    else:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("place_name")
        if not name:
            continue
        profiles[name] = build_place_profile_from_meta(item)

    print(f"📦 dessert_en 기반 매장 메타 프로필 수: {len(profiles)}")
    return profiles


def get_place_profile(
    place_name: str,
    profiles: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if place_name in profiles:
        return profiles[place_name]

    return {
        "is_beverage_shop": False,
        "menu_keywords": set(),
        "beverage_score": 0,
        "dessert_score": 0,
    }


# ============================================================
# 4. 규칙 기반 추출 + 부정 문맥 처리
# ============================================================

def normalize_text_for_rule(text: str) -> str:
    # 공백 제거 + 소문자
    return re.sub(r"\s+", "", text).lower()


def is_negated_keyword(kw_norm: str, text_norm: str) -> bool:
    """
    kw_norm: 공백/대소문자 제거된 키워드 (예: '바삭바삭', '웨이팅')
    text_norm: 공백 제거된 리뷰 전체 텍스트
    - '바삭바삭하지않다', '안바삭바삭함', '웨이팅없다', '웨이팅안하고' 등
      부정/부정적 상황이면 True를 반환.
    """
    # 키워드 주변 8글자 정도 윈도우 안에서 부정 패턴만 확인
    idx = 0
    while True:
        idx = text_norm.find(kw_norm, idx)
        if idx == -1:
            break

        start = max(0, idx - 8)
        end = min(len(text_norm), idx + len(kw_norm) + 8)
        window = text_norm[start:end]

        # 1) "키워드+하지않/지않/없다/없음/없어서" 패턴
        if re.search(
            kw_norm + r"(하지않|지않|지않고|지않았|없다|없고|없어서|없어|없음)",
            window
        ):
            return True

        # 2) "안/못/별로/전혀/그닥/그다지 + 키워드" 패턴
        if re.search(
            r"(안|못|별로|전혀|그닥|그다지)[^가-힣0-9]*" + kw_norm,
            window
        ):
            return True

        # 3) "키워드 + 느낌이없다/느낌안난다" 확장 패턴
        if re.search(
            kw_norm + r"[^가-힣0-9]*(느낌이없|느낌안나|느낌이안나)",
            window
        ):
            return True

        idx += len(kw_norm)

    return False


def has_positive_occurrence(kw: str, text_norm: str) -> bool:
    """
    리뷰 텍스트(공백 제거) 안에서:
      - 해당 키워드가 등장하고
      - 부정 문맥이 아니라면
    True를 반환.
    """
    kw_norm = kw.replace(" ", "").lower()
    if not kw_norm:
        return False

    if kw_norm not in text_norm:
        return False

    if is_negated_keyword(kw_norm, text_norm):
        return False

    return True


def rule_based_extract_keywords(
    text: str,
    kw_by_cat: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """
    규칙 기반 키워드 추출:
    - 텍스트에 키워드가 실제 등장하고
    - 부정 문맥이 아닌 경우만 hit 로 인정
    """
    norm = normalize_text_for_rule(text)
    hits = {
        "menu": [],
        "taste": [],
        "texture": [],
        "topping": [],
        "store": [],
    }

    for cat, kw_list in kw_by_cat.items():
        for kw in kw_list:
            if has_positive_occurrence(kw, norm):
                hits[cat].append(kw)

    for cat in hits:
        hits[cat] = sorted(list(set(hits[cat])))
    return hits


def detect_kw_surface_in_reviews(
    reviews: List[Dict[str, Any]],
    candidate_keywords: List[str],
) -> Dict[str, bool]:
    """
    place_final_keywords 중에서
    - 실제 리뷰 텍스트에서
    - '긍정/중립 문맥'으로 한 번 이상 등장한 키워드만 True.
    """
    norm_reviews = []
    for rv in reviews:
        txt = rv.get("review_content", "")
        if not txt:
            continue
        norm_reviews.append(normalize_text_for_rule(txt))

    seen = {kw: False for kw in candidate_keywords}
    for kw in candidate_keywords:
        if not kw:
            continue
        kw_norm = kw.replace(" ", "").lower()
        if not kw_norm:
            continue

        for ntxt in norm_reviews:
            if has_positive_occurrence(kw, ntxt):
                seen[kw] = True
                break
    return seen


def make_review_text_concat(reviews: List[Dict[str, Any]]) -> str:
    texts = [r.get("review_content", "") for r in reviews if r.get("review_content", "")]
    return "\n".join(texts)


# ============================================================
# 5. 학습 데이터 로딩 (JSON 학습용 – 지금은 DB 추론에서는 사용하지 않음)
# ============================================================

def load_train_data(
    train_dir: str,
    label2id: Dict[str, int],
    kw_by_cat: Dict[str, List[str]],
    place_profiles: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    train_ver2 안의 각 JSON (매장 단위 데이터)을 읽어
    리뷰 단위 학습 샘플을 구성한다.
    """
    samples: List[Dict[str, Any]] = []
    files = [f for f in os.listdir(train_dir) if f.endswith(".json")]
    print(f"📂 학습 파일 개수: {len(files)}")

    for fname in files:
        path = os.path.join(train_dir, fname)
        data = load_json(path)
        place = data.get("place_name", fname)

        profile = get_place_profile(place, place_profiles)
        is_beverage_shop = profile["is_beverage_shop"]

        kw_obj = data.get("keywords", {})
        place_final_keywords = kw_obj.get("final_keywords", [])
        place_final_keywords = [k for k in place_final_keywords if k in label2id]

        reviews = data.get("reviews", [])
        if not reviews:
            continue

        # place_final_keywords 중 실제 리뷰에서 "긍정 문맥"으로 등장한 것만 남기기
        seen_map = detect_kw_surface_in_reviews(reviews, place_final_keywords)
        filtered_final_keywords = [k for k in place_final_keywords if seen_map.get(k, False)]
        place_final_keywords = filtered_final_keywords

        if not place_final_keywords:
            continue

        for rv in reviews:
            text = rv.get("review_content", "").strip()
            if not text:
                continue

            # 개별 리뷰 수준 rule-based hit (부정 문맥 제거 반영됨)
            rule_hits = rule_based_extract_keywords(text, kw_by_cat)
            rule_final = []
            for cat in ["menu", "taste", "texture", "topping", "store"]:
                rule_final.extend(rule_hits.get(cat, []))

            merged_labels = set(place_final_keywords) | set(rule_final)
            merged_labels = [k for k in merged_labels if k in label2id]

            if not merged_labels:
                continue

            label_vec = np.zeros(len(label2id), dtype=np.float32)
            for k in merged_labels:
                label_vec[label2id[k]] = 1.0

            samples.append(
                {
                    "text": text,
                    "labels": label_vec,
                    "place_name": place,
                    "is_beverage_shop": is_beverage_shop,
                }
            )

    print(f"✅ 생성된 학습 샘플 수: {len(samples)}")
    return samples


# ============================================================
# 6. Dataset / Dataloader
# ============================================================

class ReviewDataset(Dataset):
    def __init__(
        self,
        samples: List[Dict[str, Any]],
        tokenizer: AutoTokenizer,
        max_len: int,
    ):
        self.samples = samples
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int):
        item = self.samples[idx]
        text = item["text"]
        labels = item["labels"]

        enc = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )

        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(labels, dtype=torch.float32),
        }


def create_dataloader(dataset: Dataset, batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0)


# ============================================================
# 7. 모델 정의
# ============================================================

class KeywordExtractorModel(nn.Module):
    def __init__(self, num_labels: int):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(BASE_MODEL_NAME)
        hidden_size = self.encoder.config.hidden_size
        self.classifier = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state[:, 0, :]  # [CLS] 토큰
        logits = self.classifier(pooled)
        return logits


# ============================================================
# 8. pos_weight + 카테고리별 loss 가중치
# ============================================================

def compute_pos_weight(samples: List[Dict[str, Any]], num_labels: int) -> torch.Tensor:
    label_sum = np.zeros(num_labels, dtype=np.float64)
    for s in samples:
        label_sum += s["labels"]

    n_samples = len(samples)
    pos = label_sum
    neg = n_samples - pos

    pos = np.clip(pos, 1.0, None)
    neg = np.clip(neg, 1.0, None)

    pos_weight = neg / pos
    pos_weight = np.clip(pos_weight, 1.0, 5.0)

    print("📊 pos_weight 통계")
    print(f"  - min: {pos_weight.min():.3f}")
    print(f"  - max: {pos_weight.max():.3f}")
    print(f"  - mean: {pos_weight.mean():.3f}")
    return torch.tensor(pos_weight, dtype=torch.float32)


def build_label_loss_weights(
    label_list: List[str],
    kw2cat: Dict[str, str],
) -> torch.Tensor:
    """
    taste/texture/topping 은 loss 가중치를 조금 더 높게,
    store 는 살짝 높게, menu 는 기본값 1.0
    """
    w = np.ones(len(label_list), dtype=np.float32)
    for i, kw in enumerate(label_list):
        cat = kw2cat.get(kw, "menu")
        if cat in ["taste", "texture", "topping"]:
            w[i] = 1.5
        elif cat == "store":
            w[i] = 1.2
        else:
            w[i] = 1.0

    print("📊 카테고리별 label_loss_weights 설정 완료")
    return torch.tensor(w, dtype=torch.float32)


# ============================================================
# 9. K-Fold 유틸
# ============================================================

def make_kfold_indices(n_samples: int, k: int, seed: int = 42):
    indices = list(range(n_samples))
    rng = random.Random(seed)
    rng.shuffle(indices)

    fold_sizes = [n_samples // k] * k
    for i in range(n_samples % k):
        fold_sizes[i] += 1

    current = 0
    folds = []
    for fs in fold_sizes:
        start, stop = current, current + fs
        folds.append(indices[start:stop])
        current = stop

    for i in range(k):
        val_idx = folds[i]
        train_idx = [idx for j, f in enumerate(folds) if j != i for idx in f]
        yield train_idx, val_idx


# ============================================================
# 10. 학습 루프
# ============================================================

def train_one_fold(
    fold_id: int,
    train_samples: List[Dict[str, Any]],
    val_samples: List[Dict[str, Any]],
    label_list: List[str],
    kw2cat: Dict[str, str],
    pos_weight: torch.Tensor,
):
    print("------------------------------------------------------------")
    print(f"📂 Fold {fold_id} 학습 시작 (train {len(train_samples)}, val {len(val_samples)})")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    train_dataset = ReviewDataset(train_samples, tokenizer, MAX_SEQ_LEN)
    val_dataset = ReviewDataset(val_samples, tokenizer, MAX_SEQ_LEN)

    train_loader = create_dataloader(train_dataset, BATCH_SIZE, True)
    val_loader = create_dataloader(val_dataset, BATCH_SIZE, False)

    model = KeywordExtractorModel(num_labels=len(label_list)).to(DEVICE)

    label_loss_weights = build_label_loss_weights(label_list, kw2cat).to(DEVICE)
    pos_weight = pos_weight.to(DEVICE)

    no_decay = ["bias", "LayerNorm.weight"]
    encoder_params, classifier_params = [], []

    for name, param in model.named_parameters():
        if "classifier" in name:
            classifier_params.append((name, param))
        else:
            encoder_params.append((name, param))

    optimizer_grouped_parameters = [
        {
            "params": [p for n, p in encoder_params if not any(nd in n for nd in no_decay)],
            "weight_decay": 0.01,
            "lr": BASE_LR,
        },
        {
            "params": [p for n, p in encoder_params if any(nd in n for nd in no_decay)],
            "weight_decay": 0.0,
            "lr": BASE_LR,
        },
        {
            "params": [p for n, p in classifier_params if not any(nd in n for nd in no_decay)],
            "weight_decay": 0.01,
            "lr": HEAD_LR,
        },
        {
            "params": [p for n, p in classifier_params if any(nd in n for nd in no_decay)],
            "weight_decay": 0.0,
            "lr": HEAD_LR,
        },
    ]
    optimizer = torch.optim.AdamW(optimizer_grouped_parameters)

    def bce_with_pos_and_cat(logits, labels):
        loss_per_label = F.binary_cross_entropy_with_logits(
            logits,
            labels,
            pos_weight=pos_weight,
            reduction="none",
        )
        loss_per_label = loss_per_label * label_loss_weights
        return loss_per_label.mean()

    best_val = float("inf")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        tr_loss, tr_steps = 0.0, 0

        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            logits = model(input_ids, attention_mask)
            loss = bce_with_pos_and_cat(logits, labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            tr_loss += loss.item()
            tr_steps += 1

        tr_loss /= max(tr_steps, 1)

        model.eval()
        val_loss, val_steps = 0.0, 0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(DEVICE)
                attention_mask = batch["attention_mask"].to(DEVICE)
                labels = batch["labels"].to(DEVICE)

                logits = model(input_ids, attention_mask)
                loss = bce_with_pos_and_cat(logits, labels)

                val_loss += loss.item()
                val_steps += 1

        val_loss /= max(val_steps, 1)
        print(f"[Fold {fold_id}] Epoch {epoch}/{EPOCHS} - train_loss: {tr_loss:.4f}, val_loss: {val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss

    return best_val


def run_kfold_training(
    samples: List[Dict[str, Any]],
    label_list: List[str],
    kw2cat: Dict[str, str],
):
    pos_weight = compute_pos_weight(samples, len(label_list))
    n_samples = len(samples)
    fold_losses = []

    if K_FOLD <= 1:
        print("============================================================")
        print("🚀 단일 train/val 학습 시작 (K_FOLD=1)")
        print("============================================================")

        idx = list(range(n_samples))
        random.shuffle(idx)
        split = int(n_samples * 0.8)
        train_idx, val_idx = idx[:split], idx[split:]
        train_samples = [samples[i] for i in train_idx]
        val_samples = [samples[i] for i in val_idx]

        val_loss = train_one_fold(1, train_samples, val_samples, label_list, kw2cat, pos_weight)
        fold_losses.append(val_loss)
    else:
        print("============================================================")
        print(f"🚀 K-Fold 학습 시작 (K={K_FOLD})")
        print("============================================================")
        for fold_id, (train_idx, val_idx) in enumerate(
            make_kfold_indices(n_samples, K_FOLD, seed=42), start=1
        ):
            train_samples = [samples[i] for i in train_idx]
            val_samples = [samples[i] for i in val_idx]
            val_loss = train_one_fold(fold_id, train_samples, val_samples, label_list, kw2cat, pos_weight)
            fold_losses.append(val_loss)

    print("============================================================")
    print("✅ K-Fold/단일 학습 종료")
    for i, l in enumerate(fold_losses, start=1):
        print(f"  - Fold {i} val_loss: {l:.4f}")
    print(f"  - 평균 val_loss: {np.mean(fold_losses):.4f}")
    print("============================================================")

    # ---------------------------------------------------------
    # 전체 데이터로 최종 모델 학습
    # ---------------------------------------------------------
    print("📦 전체 데이터로 최종 모델 학습 시작")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    full_dataset = ReviewDataset(samples, tokenizer, MAX_SEQ_LEN)
    full_loader = create_dataloader(full_dataset, BATCH_SIZE, True)

    model = KeywordExtractorModel(num_labels=len(label_list)).to(DEVICE)
    label_loss_weights = build_label_loss_weights(label_list, kw2cat).to(DEVICE)
    pos_weight_tensor = compute_pos_weight(samples, len(label_list)).to(DEVICE)

    no_decay = ["bias", "LayerNorm.weight"]
    encoder_params, classifier_params = [], []
    for name, param in model.named_parameters():
        if "classifier" in name:
            classifier_params.append((name, param))
        else:
            encoder_params.append((name, param))

    optimizer_grouped_parameters = [
        {
            "params": [p for n, p in encoder_params if not any(nd in n for nd in no_decay)],
            "weight_decay": 0.01,
            "lr": BASE_LR,
        },
        {
            "params": [p for n, p in encoder_params if any(nd in n for nd in no_decay)],
            "weight_decay": 0.0,
            "lr": BASE_LR,
        },
        {
            "params": [p for n, p in classifier_params if not any(nd in n for nd in no_decay)],
            "weight_decay": 0.01,
            "lr": HEAD_LR,
        },
        {
            "params": [p for n, p in classifier_params if any(nd in n for nd in no_decay)],
            "weight_decay": 0.0,
            "lr": HEAD_LR,
        },
    ]
    optimizer = torch.optim.AdamW(optimizer_grouped_parameters)

    def bce_full(logits, labels):
        loss_per_label = F.binary_cross_entropy_with_logits(
            logits,
            labels,
            pos_weight=pos_weight_tensor,
            reduction="none",
        )
        loss_per_label = loss_per_label * label_loss_weights
        return loss_per_label.mean()

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss, steps = 0.0, 0
        for batch in full_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            logits = model(input_ids, attention_mask)
            loss = bce_full(logits, labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()
            steps += 1
        avg_loss = total_loss / max(steps, 1)
        print(f"[FULL] Epoch {epoch}/{EPOCHS} - loss: {avg_loss:.4f}")


    # 최종 모델 저장 경로는 "현재 작업 디렉터리" 기준
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "label_list": label_list,
            "kw2cat": kw2cat,
            "config": {
                "BASE_MODEL_NAME": BASE_MODEL_NAME,
                "MAX_SEQ_LEN": MAX_SEQ_LEN,
            },
        },
        CHECKPOINT_PATH,
    )
    print(f"✅ 최종 모델 저장 완료 → {CHECKPOINT_PATH}")


# ============================================================
# 11. 리뷰 컨텍스트(bread/beverage/generic) 판별
# ============================================================

BREAD_WORDS = [
    "빵", "크로와상", "크루아상", "도넛", "도너츠",
    "꽈배기", "크로플", "스콘", "타르트", "마카롱",
    "마들렌", "휘낭시에", "까눌레", "베이글",
    "케이크", "롤케이크", "브라우니", "파이",
    "식빵", "바게트", "호밀빵", "쿠키",
]

# 빵/음료 재료형 키워드 (과일/견과 등)
INGREDIENT_LIKE_KEYWORDS = {
    "고구마", "단호박", "밤", "피칸", "피스타치오", "헤이즐넛",
    "딸기", "망고", "레몬", "귤", "자몽", "오렌지", "포도",
    "블루베리", "체리", "무화과", "바나나",
}


def classify_review_context(
    text: str,
    place_profile: Dict[str, Any],
) -> str:
    norm = normalize_text_for_rule(text)
    has_bread = any(w in norm for w in BREAD_WORDS)
    has_bev = any(w in norm for w in BEVERAGE_TOKENS)

    if has_bread:
        return "bread"
    if has_bev:
        return "beverage"
    return "generic"


# ============================================================
# 12. 추론용: 모델 로드 & 예측
# ============================================================

def load_trained_model_for_inference():
    """
    DB 기반 추론에서 사용하는 함수.
    체크포인트 경로는 model_ver11.py가 있는 디렉터리 기준으로 찾는다.
    """
    model_dir = os.path.dirname(__file__)
    ckpt_path = os.path.join(model_dir, CHECKPOINT_PATH)

    print(f"🔍 CKPT PATH: {ckpt_path}")

    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"체크포인트 파일을 찾을 수 없습니다: {ckpt_path}")

    ckpt = torch.load(ckpt_path, map_location=DEVICE)
    label_list = ckpt["label_list"]
    kw2cat = ckpt["kw2cat"]
    cfg = ckpt["config"]

    model = KeywordExtractorModel(num_labels=len(label_list))
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(DEVICE)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(cfg["BASE_MODEL_NAME"])
    return model, tokenizer, label_list, kw2cat


def predict_keywords_for_texts(
    texts: List[str],
    model: KeywordExtractorModel,
    tokenizer: AutoTokenizer,
    label_list: List[str],
    kw_by_cat: Dict[str, List[str]],
    kw2cat: Dict[str, str],
    place_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    - 리뷰 리스트(texts)를 받아 키워드 분류 + rule-based 보완 + 부정 문맥 제거
    - 각 키워드별 '양성 리뷰 수(pos_count)'와 '비율(ratio)'까지 함께 반환
    """
    if not texts:
        return {
            "menu_labels": [],
            "topping_labels": [],
            "taste_labels": [],
            "texture_labels": [],
            "store_labels": [],
            "final_keywords": [],
            "keyword_stats": {},
        }

    if place_profile is None:
        place_profile = {
            "is_beverage_shop": False,
            "menu_keywords": set(),
            "beverage_score": 0,
            "dessert_score": 0,
        }

    is_beverage_shop = place_profile.get("is_beverage_shop", False)

    idx_by_cat = {"menu": [], "topping": [], "taste": [], "texture": [], "store": []}
    for i, kw in enumerate(label_list):
        cat = kw2cat.get(kw, "menu")
        if cat in idx_by_cat:
            idx_by_cat[cat].append(i)

    # 키워드가 "빵 컨텍스트에서 등장했는지" 기록
    kw_seen_in_bread_ctx: Dict[str, bool] = {kw: False for kw in label_list}
    # 키워드가 "긍정/중립 문맥"으로 등장한 리뷰 수
    kw_positive_counts: Dict[str, int] = {kw: 0 for kw in label_list}

    all_probs = []
    for text in texts:
        ctx = classify_review_context(text, place_profile)
        norm = normalize_text_for_rule(text)

        # 긍정 문맥 등장 카운트
        for kw in label_list:
            if has_positive_occurrence(kw, norm):
                kw_positive_counts[kw] += 1

        enc = tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=MAX_SEQ_LEN,
            return_tensors="pt",
        )

        with torch.no_grad():
            logits = model(
                input_ids=enc["input_ids"].to(DEVICE),
                attention_mask=enc["attention_mask"].to(DEVICE),
            )
            probs = torch.sigmoid(logits).cpu().numpy()[0]

        # 음료 컨텍스트에서는 taste/topping 차단
        if ctx == "beverage" or (ctx == "generic" and is_beverage_shop):
            for idx in idx_by_cat["topping"]:
                probs[idx] = 0.0
            for idx in idx_by_cat["taste"]:
                probs[idx] = 0.0

        # 빵 컨텍스트(또는 빵 위주 generic)에서는
        # 실제 등장한 키워드를 모두 "빵 문맥에서 본 것"으로 기록
        if (ctx == "bread") or (ctx == "generic" and not is_beverage_shop):
            for kw in label_list:
                kw_norm = kw.replace(" ", "").lower()
                if kw_norm and kw_norm in norm:
                    kw_seen_in_bread_ctx[kw] = True

        all_probs.append(probs)

    avg_probs = np.mean(all_probs, axis=0)
    kw_scores = {kw: avg_probs[i] for i, kw in enumerate(label_list)}

    base_thresh_menu = 0.5
    base_thresh_oth = 0.4

    menu_labels, topping_labels, taste_labels = [], [], []
    texture_labels, store_labels = [], []

    for kw, score in kw_scores.items():
        cat = kw2cat.get(kw, "menu")
        if cat == "menu":
            if score >= base_thresh_menu:
                menu_labels.append(kw)
        elif cat == "topping":
            if score >= base_thresh_oth:
                topping_labels.append(kw)
        elif cat == "taste":
            if score >= base_thresh_oth:
                taste_labels.append(kw)
        elif cat == "texture":
            if score >= base_thresh_oth:
                texture_labels.append(kw)
        elif cat == "store":
            if score >= base_thresh_oth:
                store_labels.append(kw)

    # 리뷰 전체 텍스트 합치기
    concat_text = "\n".join(texts)
    concat_norm = normalize_text_for_rule(concat_text)

    # rule-based (전체 리뷰 기준, 부정 문맥 제거 포함)
    rb_hits = rule_based_extract_keywords(concat_text, kw_by_cat)
    for k in rb_hits.get("menu", []):
        if k not in menu_labels and k in label_list:
            menu_labels.append(k)
    for k in rb_hits.get("topping", []):
        if k not in topping_labels and k in label_list:
            topping_labels.append(k)
    for k in rb_hits.get("taste", []):
        if k not in taste_labels and k in label_list:
            taste_labels.append(k)
    for k in rb_hits.get("texture", []):
        if k not in texture_labels and k in label_list:
            texture_labels.append(k)
    for k in rb_hits.get("store", []):
        if k not in store_labels and k in label_list:
            store_labels.append(k)

    # taste/topping은 "빵 컨텍스트에서 실제 등장" + "긍정 문맥 등장" 둘 다 필요
    def filter_taste_topping(kws: List[str]) -> List[str]:
        kept = []
        for k in kws:
            if not kw_seen_in_bread_ctx.get(k, False):
                continue
            if kw_positive_counts.get(k, 0) <= 0:
                continue
            kept.append(k)
        return kept

    topping_labels = filter_taste_topping(topping_labels)
    taste_labels = filter_taste_topping(taste_labels)

    # menu/store/texture 도 "긍정 문맥으로 등장한 적이 있는 키워드"만 유지
    def filter_by_positive_count(kws: List[str]) -> List[str]:
        return [k for k in kws if kw_positive_counts.get(k, 0) > 0]

    menu_labels = filter_by_positive_count(menu_labels)
    store_labels = filter_by_positive_count(store_labels)
    texture_labels = filter_by_positive_count(texture_labels)

    # 음료 위주 카페에서는 재료형 키워드(INGREDIENT_LIKE_KEYWORDS)가
    # 빵 컨텍스트에서 등장하지 않았다면 제거
    if is_beverage_shop:
        filtered_menu = []
        for k in menu_labels:
            if k in INGREDIENT_LIKE_KEYWORDS and not kw_seen_in_bread_ctx.get(k, False):
                continue
            filtered_menu.append(k)
        menu_labels = filtered_menu

    menu_labels = sorted(set(menu_labels))
    topping_labels = sorted(set(topping_labels))
    taste_labels = sorted(set(taste_labels))
    texture_labels = sorted(set(texture_labels))
    store_labels = sorted(set(store_labels))

    final_keywords = sorted(
        set(menu_labels + topping_labels + taste_labels + texture_labels + store_labels)
    )

    # --------------------------------------------------------
    # 각 키워드별 '양성 리뷰 수' / '비율' 계산
    # --------------------------------------------------------
    num_reviews = len(texts)
    kw_ratio = {
        kw: (kw_positive_counts[kw] / num_reviews) if num_reviews > 0 else 0.0
        for kw in label_list
    }

    keyword_stats = {
        kw: {
            "pos_count": int(kw_positive_counts[kw]),
            "ratio": float(kw_ratio[kw]),
        }
        for kw in final_keywords
    }

    return {
        "menu_labels": menu_labels,
        "topping_labels": topping_labels,
        "taste_labels": taste_labels,
        "texture_labels": texture_labels,
        "store_labels": store_labels,
        "final_keywords": final_keywords,
        # 나중에 "에그타르트 맛집 재정렬" 등에 활용할 수 있는 정보
        "keyword_stats": keyword_stats,
    }


def run_predict_folder(test_dir: str = "test"):
    """
    test_dir 안의 JSON(매장 단위)을 읽어서
    - reviews → 키워드 예측
    - data["keywords"]를 덮어쓰고 다시 저장
    """
    # 체크포인트 경로를 model_ver11.py 기준으로 보정
    model_dir = os.path.dirname(__file__)
    ckpt_path = os.path.join(model_dir, CHECKPOINT_PATH)

    if not os.path.exists(ckpt_path):
        print(f"❌ 체크포인트가 없습니다: {ckpt_path}")
        return

    base_kw_path = os.path.join(model_dir, BASE_KEYWORD_PATH)
    new_kw_path = os.path.join(model_dir, NEW_KEYWORD_PATH)
    dessert_meta_path = os.path.join(model_dir, DESSERT_META_PATH)

    kw_by_cat, label_list_all, label2id, id2label, kw2cat = load_keyword_config(
        base_kw_path, new_kw_path
    )
    place_profiles = load_dessert_profiles(dessert_meta_path)
    model, tokenizer, label_list_ckpt, kw2cat_ckpt = load_trained_model_for_inference()

    if label_list_ckpt != label_list_all:
        print("⚠️ 주의: 체크포인트의 label_list와 현재 키워드 구성이 다를 수 있습니다.")

    files = [f for f in os.listdir(test_dir) if f.endswith(".json")]
    print(f"📂 테스트 파일 개수: {len(files)}")

    for fname in files:
        path = os.path.join(test_dir, fname)
        data = load_json(path)
        place = data.get("place_name", fname)

        profile = get_place_profile(place, place_profiles)
        reviews = data.get("reviews", [])
        texts = [r.get("review_content", "") for r in reviews if r.get("review_content", "")]

        print("=" * 60)
        print(f"🏷  {fname} | 매장명: {place} | 리뷰 {len(texts)}개")

        kw_result = predict_keywords_for_texts(
            texts, model, tokenizer, label_list_ckpt, kw_by_cat, kw2cat_ckpt, place_profile=profile
        )
        data["keywords"] = kw_result
        save_json(data, path)
        print(f"  ✅ 예측된 키워드: {kw_result['final_keywords']}")
        print(f"  💾 저장 완료 → {path}")


# ============================================================
# 13. main (JSON 학습/테스트용, DB 추론과는 별개)
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["train", "predict-folder"],
        help="train: 모델 학습 / predict-folder: 폴더 내 JSON 예측",
    )
    parser.add_argument(
        "--test_dir",
        type=str,
        default="test",
        help="predict-folder 모드에서 사용할 폴더 경로",
    )
    args = parser.parse_args()

    set_seed(42)
    # model_ver11.py 파일이 있는 디렉터리 기준으로 경로 보정
    model_dir = os.path.dirname(__file__)
    base_kw_path = os.path.join(model_dir, BASE_KEYWORD_PATH)
    new_kw_path = os.path.join(model_dir, NEW_KEYWORD_PATH)
    dessert_meta_path = os.path.join(model_dir, DESSERT_META_PATH)
    if args.mode == "train":
        print("============================================================")
        print("🍞 KoELECTRA 키워드 추출 모델 학습 시작 (ver11)")
        print("============================================================")
        kw_by_cat, label_list, label2id, id2label, kw2cat = load_keyword_config(
            base_kw_path, new_kw_path
        )
        place_profiles = load_dessert_profiles(dessert_meta_path)
        samples = load_train_data(TRAIN_DIR, label2id, kw_by_cat, place_profiles)
        run_kfold_training(samples, label_list, kw2cat)

    elif args.mode == "predict-folder":
        run_predict_folder(args.test_dir)


if __name__ == "__main__":
    main()

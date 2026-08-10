# 역할 — M4 시나리오를 스토리보드 이미지 계획 + Seedance 영상 프롬프트로 전환

아래 M4 시나리오(등장인물/컷별 구성 — 각 컷은 background/camera/action/music/dialogue/
text_overlay 타입의 beats 로 이루어져 있다)와 M0 제품 사실을 참고해, 정확히 아래 구조를
완성하라. beats 중 background·camera·action 만 시각 정보다 — music·dialogue·text_overlay 는
이미지/영상 생성 대상이 아니므로 무시하라(대사는 별도 더빙/자막 단계의 몫이다).

## 1) 인물 (`characters[]`)
M4 `cast[]`에 있는 인물마다 하나씩(같은 `id`를 그대로 이어받는다):
- `front_prompt`: 정면 — 표정이 잘 보이는 구도. 헤어·체형·인상·의상을 포함한 전체 외형 묘사
- `profile_prompt`: 측면 — 옆모습·목선이 보이는 구도. front_prompt와 동일 인물 묘사를
  반복하고 각도만 바꾼다
- `costume_prompt`: 의상 착용 — 의상의 소재·색·핏이 잘 보이는 상반신 또는 전신 구도.
  마찬가지로 동일 인물 묘사를 반복한다

## 2) 제품 (`product`) — 생성이 아니라 소싱 브리프
- `shot_briefs`: 정확히 3개 — 각 슬롯이 "무엇을 보여줘야 하는지"를 정한다(예: "정면에서 본
  전체 형태와 브랜드 로고가 함께 보이는 히어로 앵글", "펀칭 디테일이 보이는 근접 클로즈업",
  "실제 착용/사용 순간"). module0 제품 사실(외형·재질·색)에 근거하고, 서로 다른 각도/사용
  상태로 다양화하라. "생성해서 그려라"가 아니라 "실물 사진 중 이 조건에 맞는 것을 배치하거나
  찾아라"라는 전제로 써라
- `logo_brief`: 브랜드 로고 슬롯 요구사항 — 로고를 왜곡하거나 새로 만들어내지 말고 실물
  그대로 재현/배치하라는 전제로 써라

## 3) Environment (`environment`)
- `prompt`: M4 시나리오의 모든 컷이 공유하는 대표 공간을 하나로 종합한 생성 프롬프트(장소·
  실내외·시간대·톤을 포함) — 특정 실존 로케이션이 언급되지 않는 한 콘셉트 공간으로 생성한다

## 4) 컷별 (`cuts[]`)
M4 `scenes[]` 컷 수·순서를 그대로 이어받아(같은 `cut_index`) 컷마다 두 개를 분리해서 써라:
- `keyframe_image_prompt`: 그 컷의 대표 순간 하나를 정지 이미지로 그리는 프롬프트. 해당 컷의
  background(공간)·action(인물의 정지된 자세/표정)·camera(사이즈·앵글)를 반영한 구도 묘사.
  등장하는 인물/제품/공간은 위 1)·2)·3)에서 고정한 묘사와 반드시 일치시켜라
- `seedance_prompt`: 그 키프레임에서 영상이 어떻게 전개되는지만 서술 — 해당 컷의 action이
  시간에 따라 어떻게 진행되는지(동작의 시작→끝), camera beat 에 카메라 무브먼트가 있으면
  그 움직임(예: 돌리인·패닝·틸트)을 명시하라. 인물 외형·제품 형태·공간 디테일 같은 정적
  정보는 절대 반복하지 마라 — 오직 "무엇이 움직이는가"만 써라

# 출력
JSON 객체 하나만:
`{"characters":[{"id","front_prompt","profile_prompt","costume_prompt"},...],"product":{"shot_briefs":["...","...","..."],"logo_brief"},"environment":{"prompt"},"cuts":[{"cut_index","keyframe_image_prompt","seedance_prompt"},...]}`
코드펜스·설명·머리말 없이, `{`로 시작해 `}`로 끝난다.

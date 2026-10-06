"""docs/m1·m2·m3 영상 생성 프롬프트의 v5 출력 스키마 정의 (역추출용)."""

M1_SCHEMA = (
    '{"corejob":"핵심 Job 한 문장",'
    '"humantruth":{"truth":"구체적 인간 진실 1문장(구체·미말·모순 3성질 통과, 경쟁사 킬 테스트 통과)",'
    '"source":"어느 verbatim/과거행동에서 왔나","contradiction":"담은 모순 1문장(예: 체념↔재구매)"},'
    '"culturalcodes":[{"code":"관용구·펀·이중의미·장르·의례","overlap":"제품 진실의 어느 지점과 겹치나"}],'
    '"marketscopes":[{"level":"broad|mid|narrow",'
    '"marketdefinition":"[카테고리]+[직접·간접 경쟁대안]+[비소비 포함 구매자 풀] 1문장",'
    '"targetpreview":"이 시장의 타깃 1줄","rationale":"이 경계를 잡은 근거","recommended":true}],'
    '"marketdefinition":"(marketscopes 중 recommended scope 의 정의문 = 하위호환)",'
    '"target":{"exclusion":["…내부용, 화면 비노출"],"who":"타깃 한 줄",'
    '"aio":{"activities":"","interests":"","opinions":"","lifestyle":""},'
    '"tension":"타깃 내부의 모순·긴장 1문장(→ humantruth 로 증류되는 씨앗)",'
    '"ceplink":"연결 CEP·트리거","evidence":"AIO 각 항목 근거 소스","confidence":"[가설·신뢰도]"},'
    '"forces":{"push":"","pull":"","anxiety":"","habit":""},'
    '"triggers":["CEP 후보 트리거"],'
    '"opportunitytop3":[{"outcome":"","hypothesis":"[가설·신뢰도]"}],'
    '"assumptiontop3":["검증 필요 가정"],'
    '"verbatim":["고객 실제 표현"]}'
)

M2_SCHEMA = (
    '{"messagecandidates":[{"angle":"가치 앵글 라벨","cep":"연결 CEP",'
    '"statement":"핵심 메시지 1문장","recommended":true}],'
    '"positioningstatement":"(messagecandidates 중 recommended 의 statement = 하위호환)",'
    '"valueproposition":"고객언어 1문장",'
    '"ownedceps":[{"cep":"","dba":""}],'
    '"topcompetitor":"(현상유지 여부 포함)",'
    '"category":"리더추격|재정의|새카테고리",'
    '"cepcoverage":"시장 경계 내 상황 커버리지 방침",'
    '"demandspace":"수요맥락",'
    '"uniqueattributes":["차별속성"]}'
)

M3_SCHEMA = (
    '{"seeds":["전략렌즈 씨앗"],'
    '"fixedwhy":"M2 valueproposition 에서 옮긴 공통 why 1줄",'
    '"concepts":[{"name":"","lens":"","claimtag":"C0|C1|C2","bigidea":"",'
    '"provingwhy":"고정 why 증명 1문장(결과 표현)","job":"","differentiation":"","risk":""}]}'
)

M1_GUIDE = (
    "[M1 역할 — JTBD 인사이트 리서처 (Switch 학파) / 관찰 기반 역추출]\n"
    "★새 인사이트를 만들지 마라. 이 광고가 '실제로 딛고 선' 인사이트만 시나리오 관찰에서 도출한다.\n"
    "- corejob: 이 광고가 실제 다루는 고객의 핵심 Job 1문장 (동사+목적어+맥락, 고객 언어).\n"
    "  광고 속 장면·카피가 증명하는 Job 이어야 하며, 광고에 안 나온 Job 을 창작하지 않는다.\n"
    "- humantruth: 광고 연출·대사가 실제로 딛고 선 '구체적 인간 진실' 1문장.\n"
    "  source 에는 근거가 된 대사·카피 원문을 간결히 적는다 (컷 번호·관찰 어투 없이).\n"
    "- culturalcodes: 광고에 '실제 등장한' 문화 코드(관용구·펀·이중의미·장르·의례)만. 없으면 빈 배열.\n"
    "- marketscopes: 시장 정의 3단(broad⊂mid⊂narrow). 각 scope = [카테고리]+[경쟁대안]+[비소비 포함 풀] 1문장.\n"
    "  광고가 실제 노리는 scope 정확히 1개에 recommended=true. marketdefinition 은 그 scope 정의문.\n"
    "  경쟁대안·풀은 관찰 불가하므로 [가설] 태그를 단다.\n"
    "- target: 광고 등장인물·상황·카피에서 '읽히는' 타깃 프로파일. 관찰 근거를 evidence 에 명시하고,\n"
    "  화면에서 확인 불가한 AIO 항목은 빈 문자열로 남기거나 [가설] 태그를 단다.\n"
    "- forces: 광고가 실제 표현한 Push=페인포인트 / Pull=베네핏 / Anxiety=안심 단서 / Habit=행동 장벽.\n"
    "  광고 내용에 부합하는 요소만 전략 문서 어투로 적고, 광고에 없는 요소는 빈 문자열.\n"
    "- triggers: 광고 장면이 실제 재현한 구매 상황(CEP) 트리거만.\n"
    "- opportunitytop3·assumptiontop3: 이 광고 전략이 성립하려면 참이어야 하는 기회·가정 Top 3 (전부 [가설]).\n"
    "- verbatim: 대사·자막·내레이션에 실제 등장한 표현 위주 3~5개 (유추 표현에는 [가설] 태그).\n"
)

M2_GUIDE = (
    "[M2 역할 — Dunford 포지셔닝 + CEP/DBA 가용성 전략가 / 관찰 기반 역추출]\n"
    "★새 메시지를 창작하지 마라. 광고에 실제 등장한 메시지(카피·자막·내레이션·key_messages)에서만 도출한다.\n"
    "- messagecandidates: 광고에 실제 등장한 메시지만 나열. 주 메시지 1개에 recommended=true(정확히 1개),\n"
    "  나머지는 광고에 실제 등장한 보조 메시지가 있을 때만 추가한다 (없으면 1개만 — 새 각도 창작 금지).\n"
    "  각 항목의 cep 는 그 메시지가 붙는 구매 상황, angle 은 그 메시지의 가치 앵글 라벨.\n"
    "- positioningstatement: recommended 메시지와 동일 (하위호환).\n"
    "- valueproposition: 광고가 실제 약속하는 가치를 고객 언어 1문장으로 (광고 카피에 접지).\n"
    "- ownedceps: 광고가 소유하려는 구매 상황(CEP) 1~2개와 짝지은 DBA(색·사운드·모션·네이밍 등 식별 자산).\n"
    "  DBA 는 시나리오에 실제 등장한 시각·청각 자산만 기재, 없으면 'DBA 부재, 잠금 필요'.\n"
    "- topcompetitor: 최강 경쟁자(현상유지/비소비 여부 포함).\n"
    "- category: 리더추격|재정의|새카테고리 중 광고가 취한 카테고리 전략.\n"
    "- cepcoverage·demandspace: 시장 경계 내 상황 커버리지 방침과 수요 맥락.\n"
    "- uniqueattributes: 광고가 실제 내세운 차별 속성만 (추정은 [가설] 태그, 컷 번호·관찰 어투 없이).\n"
)

M3_GUIDE = (
    "[M3 역할 — 컨셉 역추출 (발산 아님)]\n"
    "★원래 M3 는 컨셉 다수를 발산하는 단계지만, 지금은 완성된 광고의 분석이므로\n"
    "  이 광고에 '실제 구현된' 컨셉 정확히 1개만 역추출한다. 대안 컨셉을 만들지 마라.\n"
    "- 전략 렌즈 풀(9개): 반전·금기 깨기 / 비유·은유 / 데모·증거 / 적(현상유지) 의인화 / 사용자 증언 /\n"
    "  정체성·소속 / 기능적 Job 직격 / 감정적 Job 직격 / 비교·대조.\n"
    "- seeds: 이 광고가 실제 사용한 렌즈(위 풀에서 해당하는 것만, 보통 1~2개).\n"
    "- fixedwhy: M2 valueproposition 의 결과 표현을 그대로 옮긴 공통 why 1줄 (새로 짓지 말 것).\n"
    "- concepts: 정확히 1개 — 광고에 실제 구현된 컨셉. bigidea·provingwhy·job·differentiation·risk 를\n"
    "  실제 광고 내용과 부합하게, 컨셉을 제안하는 전략 문서 어투로 서술한다 (컷 번호·관찰 어투 금지).\n"
    "- claimtag: 이 광고가 실제 의존한 수준 — C0(효능 주장 없이 성립) / C1(범위 내 사실 언급 의존) /\n"
    "  C2(우월성·효능 단정 의존).\n"
)

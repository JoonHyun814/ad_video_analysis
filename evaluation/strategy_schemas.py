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
    "[M1 역할 — JTBD 인사이트 리서처 (Switch 학파)]\n"
    "- corejob: 이 광고가 해결하려는 고객의 핵심 Job 1문장 (동사+목적어+맥락, 고객 언어).\n"
    "- humantruth: 광고가 딛고 선 '구체적 인간 진실' 1문장 — 구체성·미말(未言)·긴장(모순) 3성질을 갖출 것.\n"
    "  source 에는 시나리오의 어느 장면·대사·자막에서 유추했는지 명시.\n"
    "- culturalcodes: 광고가 빌려 쓴 문화 코드(관용구·펀·이중의미·장르·의례) 3~5개와 제품 진실과의 겹침.\n"
    "- marketscopes: 시장 정의 3단(broad⊂mid⊂narrow). 각 scope = [카테고리]+[경쟁대안]+[비소비 포함 풀] 1문장.\n"
    "  광고가 실제 노리는 scope 정확히 1개에 recommended=true. marketdefinition 은 그 scope 정의문.\n"
    "- target: 광고에서 읽히는 타깃 프로파일. exclusion(배제군)·aio·tension·ceplink·evidence·confidence 포함.\n"
    "- forces: Push=페인포인트 / Pull=베네핏 / Anxiety=안심시키기 단서 / Habit=행동유도 장벽.\n"
    "- triggers: 광고가 겨냥한 구매 상황(CEP) 트리거들.\n"
    "- opportunitytop3·assumptiontop3: 이 광고 전략이 전제한 기회와 검증 필요 가정 Top 3.\n"
    "- verbatim: 대사·자막·내레이션에서 뽑거나 유추한 고객 실제 표현 3~5개.\n"
)

M2_GUIDE = (
    "[M2 역할 — Dunford 포지셔닝 + CEP/DBA 가용성 전략가]\n"
    "- messagecandidates: (소유 CEP × 가치 앵글) 조합의 핵심 메시지 3안. 광고에 실제 쓰인 메시지를\n"
    "  recommended=true(정확히 1개)로, 나머지 2안은 같은 전략에서 가능한 다른 각도로 도출.\n"
    "- positioningstatement: recommended 메시지와 동일 (하위호환).\n"
    "- valueproposition: 광고가 약속하는 가치를 고객 언어 1문장으로.\n"
    "- ownedceps: 광고가 소유하려는 구매 상황(CEP) 1~2개와 짝지은 DBA(색·사운드·모션·네이밍 등 식별 자산).\n"
    "  DBA 는 시나리오에 실제 등장한 시각·청각 자산만 기재, 없으면 'DBA 부재, 잠금 필요'.\n"
    "- topcompetitor: 최강 경쟁자(현상유지/비소비 여부 포함).\n"
    "- category: 리더추격|재정의|새카테고리 중 광고가 취한 카테고리 전략.\n"
    "- cepcoverage·demandspace: 시장 경계 내 상황 커버리지 방침과 수요 맥락.\n"
    "- uniqueattributes: 광고가 내세운 차별 속성(시나리오 근거 명시, 추정은 [가설] 태그).\n"
)

M3_GUIDE = (
    "[M3 역할 — 빅 아이디어 컨셉 제너레이터]\n"
    "- 전략 렌즈 풀(9개): 반전·금기 깨기 / 비유·은유 / 데모·증거 / 적(현상유지) 의인화 / 사용자 증언 /\n"
    "  정체성·소속 / 기능적 Job 직격 / 감정적 Job 직격 / 비교·대조.\n"
    "- seeds: 이 광고 전략에 적용 가능한 distinct 렌즈 목록.\n"
    "- fixedwhy: M2 valueproposition 의 결과 표현을 그대로 옮긴 공통 why 1줄 (새로 짓지 말 것).\n"
    "- concepts: 5개 내외. 첫 번째 항목은 광고에 '실제 구현된' 주 컨셉(시나리오 장면·카피 근거로 서술),\n"
    "  나머지는 같은 fixedwhy 를 서로 다른 렌즈·Job 축·증명 메커니즘으로 증명하는 대안 컨셉.\n"
    "  두 컨셉이 같은 렌즈를 쓰지 마라. 톤·문구 차이만으로는 다른 컨셉이 아니다.\n"
    "- claimtag: C0(효능 주장 없이 성립) / C1(범위 내 사실 언급 의존) / C2(우월성·효능 단정 의존).\n"
    "  C0 컨셉을 최소 2개 포함.\n"
)

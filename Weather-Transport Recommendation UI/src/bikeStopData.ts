// 서울시 25개 자치구 주요 따릉이 거점 대여소 마스터 데이터
export interface BikeStation {
  id: string
  name: string
  stationNo: string // 따릉이 대여소 번호 (예: '2301')
  district: string
  coords: [number, number] // [lng, lat]
  lineInfo: string
  rackCount: number // 총 거치대 수
  baseCrowd: number // 기본 이용 수요도 (0~100)
  rainSensitivity: number // 강수 시 이용 급감 계수 (음수)
  isPopularSpot?: boolean // 한강공원/대학가 등 대형 핫스팟
}

export const BIKE_STATIONS: BikeStation[] = [
  // ── 1. 강남·서초·송파·강동 (동남권) ──
  {
    id: 'bike-gn-exit9',
    name: '따릉이: 강남역 9번출구 앞',
    stationNo: '2301',
    district: '강남구',
    coords: [127.0264, 37.4984],
    lineInfo: '거치대 25대 (대여/반납소)',
    rackCount: 25,
    baseCrowd: 82,
    rainSensitivity: -2.8,
    isPopularSpot: true
  },
  {
    id: 'bike-samseong',
    name: '따릉이: 삼성역 5번출구(코엑스)',
    stationNo: '2307',
    district: '강남구',
    coords: [127.0612, 37.5090],
    lineInfo: '거치대 20대 (대여/반납소)',
    rackCount: 20,
    baseCrowd: 74,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-apgujeong-rodeo',
    name: '따릉이: 압구정로데오역 6번출구',
    stationNo: '2315',
    district: '강남구',
    coords: [127.0395, 37.5272],
    lineInfo: '거치대 15대 (대여/반납소)',
    rackCount: 15,
    baseCrowd: 68,
    rainSensitivity: -2.4
  },
  {
    id: 'bike-yangjae-stream',
    name: '따릉이: 양재천근린공원 입구',
    stationNo: '2342',
    district: '강남구',
    coords: [127.0452, 37.4815],
    lineInfo: '거치대 30대 (하천 자전거길 연결)',
    rackCount: 30,
    baseCrowd: 85,
    rainSensitivity: -3.2,
    isPopularSpot: true
  },
  {
    id: 'bike-express-bus-term',
    name: '따릉이: 고속터미널역 8-1번출구',
    stationNo: '2214',
    district: '서초구',
    coords: [127.0042, 37.5048],
    lineInfo: '거치대 25대 (대여/반납소)',
    rackCount: 25,
    baseCrowd: 79,
    rainSensitivity: -2.7
  },
  {
    id: 'bike-banpo-hangang',
    name: '따릉이: 반포한강공원 달빛광장',
    stationNo: '2219',
    district: '서초구',
    coords: [126.9965, 37.5115],
    lineInfo: '거치대 40대 (한강 라이딩 성지)',
    rackCount: 40,
    baseCrowd: 92,
    rainSensitivity: -3.5,
    isPopularSpot: true
  },
  {
    id: 'bike-sadang-exit11',
    name: '따릉이: 사당역 11번출구',
    stationNo: '2228',
    district: '서초구',
    coords: [126.9825, 37.4772],
    lineInfo: '거치대 20대 (대여/반납소)',
    rackCount: 20,
    baseCrowd: 78,
    rainSensitivity: -2.5
  },
  {
    id: 'bike-jamsil',
    name: '따릉이: 잠실역 8번출구(롯데타워)',
    stationNo: '2601',
    district: '송파구',
    coords: [127.1015, 37.5142],
    lineInfo: '거치대 35대 (석촌호수 연결)',
    rackCount: 35,
    baseCrowd: 86,
    rainSensitivity: -3.0,
    isPopularSpot: true
  },
  {
    id: 'bike-olympic-park',
    name: '따릉이: 올림픽공원 평화의문',
    stationNo: '2618',
    district: '송파구',
    coords: [127.1185, 37.5162],
    lineInfo: '거치대 45대 (공원 순환 라이딩)',
    rackCount: 45,
    baseCrowd: 90,
    rainSensitivity: -3.4,
    isPopularSpot: true
  },
  {
    id: 'bike-cheonho-exit3',
    name: '따릉이: 천호역 3번출구(로데오거리)',
    stationNo: '2505',
    district: '강동구',
    coords: [127.1245, 37.5392],
    lineInfo: '거치대 20대 (대여/반납소)',
    rackCount: 20,
    baseCrowd: 76,
    rainSensitivity: -2.5
  },
  {
    id: 'bike-gwangjin-bridge',
    name: '따릉이: 광진교 남단 자전거길',
    stationNo: '2512',
    district: '강동구',
    coords: [127.1215, 37.5455],
    lineInfo: '거치대 25대 (한강공원 연결)',
    rackCount: 25,
    baseCrowd: 80,
    rainSensitivity: -3.1
  },

  // ── 2. 영등포·마포·용산 (한강 수변 및 서남권) ──
  {
    id: 'bike-yeouinaru',
    name: '따릉이: 여의나루역 2번출구앞',
    stationNo: '207',
    district: '영등포구',
    coords: [126.9328, 37.5271],
    lineInfo: '거치대 50대 (여의도 한강공원)',
    rackCount: 50,
    baseCrowd: 95,
    rainSensitivity: -3.6,
    isPopularSpot: true
  },
  {
    id: 'bike-yeouido-park',
    name: '따릉이: 여의도공원 국회의사당앞',
    stationNo: '211',
    district: '영등포구',
    coords: [126.9185, 37.5312],
    lineInfo: '거치대 30대 (공원 자전거길)',
    rackCount: 30,
    baseCrowd: 84,
    rainSensitivity: -2.9
  },
  {
    id: 'bike-dangsan-exit4',
    name: '따릉이: 당산역 4번출구(한강육교)',
    stationNo: '235',
    district: '영등포구',
    coords: [126.9032, 37.5355],
    lineInfo: '거치대 25대 (한강 연결 나들목)',
    rackCount: 25,
    baseCrowd: 81,
    rainSensitivity: -2.8
  },
  {
    id: 'bike-hongdae-exit8',
    name: '따릉이: 홍대입구역 8번출구앞',
    stationNo: '108',
    district: '마포구',
    coords: [126.9248, 37.5568],
    lineInfo: '거치대 30대 (경의선숲길 연결)',
    rackCount: 30,
    baseCrowd: 88,
    rainSensitivity: -2.9,
    isPopularSpot: true
  },
  {
    id: 'bike-hapjeong-exit7',
    name: '따릉이: 합정역 7번출구앞',
    stationNo: '114',
    district: '마포구',
    coords: [126.9125, 37.5482],
    lineInfo: '거치대 20대 (망원한강공원 방면)',
    rackCount: 20,
    baseCrowd: 79,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-mangwon-hangang',
    name: '따릉이: 망원한강공원 나들목',
    stationNo: '152',
    district: '마포구',
    coords: [126.8975, 37.5542],
    lineInfo: '거치대 40대 (망원유원지)',
    rackCount: 40,
    baseCrowd: 91,
    rainSensitivity: -3.5,
    isPopularSpot: true
  },
  {
    id: 'bike-gongdeok-exit1',
    name: '따릉이: 공덕역 1번출구앞',
    stationNo: '128',
    district: '마포구',
    coords: [126.9498, 37.5435],
    lineInfo: '거치대 20대 (경의선숲길)',
    rackCount: 20,
    baseCrowd: 75,
    rainSensitivity: -2.5
  },
  {
    id: 'bike-ichon-hangang',
    name: '따릉이: 이촌한강공원 거북선나루터',
    stationNo: '812',
    district: '용산구',
    coords: [126.9745, 37.5182],
    lineInfo: '거치대 35대 (이촌 생태공원)',
    rackCount: 35,
    baseCrowd: 85,
    rainSensitivity: -3.2,
    isPopularSpot: true
  },
  {
    id: 'bike-yongsan-station',
    name: '따릉이: 용산역 광장 계단앞',
    stationNo: '835',
    district: '용산구',
    coords: [126.9655, 37.5292],
    lineInfo: '거치대 25대 (대여/반납소)',
    rackCount: 25,
    baseCrowd: 78,
    rainSensitivity: -2.6
  },

  // ── 3. 도심·서북권 (종로, 중구, 서대문, 은평) ──
  {
    id: 'bike-gwanghwamun-plaza',
    name: '따릉이: 광화문광장 해치마당',
    stationNo: '302',
    district: '종로구',
    coords: [126.9768, 37.5725],
    lineInfo: '거치대 30대 (도심 문화광장)',
    rackCount: 30,
    baseCrowd: 84,
    rainSensitivity: -2.7,
    isPopularSpot: true
  },
  {
    id: 'bike-cheonggye-plaza',
    name: '따릉이: 청계광장 소라탑앞',
    stationNo: '308',
    district: '종로구',
    coords: [126.9782, 37.5695],
    lineInfo: '거치대 25대 (청계천 자전거길 연결)',
    rackCount: 25,
    baseCrowd: 87,
    rainSensitivity: -3.0,
    isPopularSpot: true
  },
  {
    id: 'bike-seoul-station-exit15',
    name: '따릉이: 서울역 15번출구(서부역)',
    stationNo: '405',
    district: '중구',
    coords: [126.9688, 37.5545],
    lineInfo: '거치대 25대 (서울로7017 연결)',
    rackCount: 25,
    baseCrowd: 79,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-ddp',
    name: '따릉이: DDP 동대문디자인플라자',
    stationNo: '422',
    district: '중구',
    coords: [127.0092, 37.5668],
    lineInfo: '거치대 30대 (동대문 쇼핑타운)',
    rackCount: 30,
    baseCrowd: 81,
    rainSensitivity: -2.7
  },
  {
    id: 'bike-sinchon-station',
    name: '따릉이: 신촌역 2번출구 연세로',
    stationNo: '715',
    district: '서대문구',
    coords: [126.9372, 37.5562],
    lineInfo: '거치대 25대 (신촌 대학가)',
    rackCount: 25,
    baseCrowd: 85,
    rainSensitivity: -2.8,
    isPopularSpot: true
  },
  {
    id: 'bike-hongje-stream',
    name: '따릉이: 홍제천 인공폭포앞',
    stationNo: '738',
    district: '서대문구',
    coords: [126.9315, 37.5815],
    lineInfo: '거치대 20대 (홍제천 자전거길)',
    rackCount: 20,
    baseCrowd: 76,
    rainSensitivity: -3.0
  },
  {
    id: 'bike-bulgwang-exit2',
    name: '따릉이: 불광역 2번출구',
    stationNo: '912',
    district: '은평구',
    coords: [126.9312, 37.6115],
    lineInfo: '거치대 20대 (북한산생태공원 방면)',
    rackCount: 20,
    baseCrowd: 71,
    rainSensitivity: -2.4
  },
  {
    id: 'bike-eungam-stream',
    name: '따릉이: 응암역 불광천 자전거길입구',
    stationNo: '924',
    district: '은평구',
    coords: [126.9162, 37.5992],
    lineInfo: '거치대 35대 (불광천 라이딩 코스)',
    rackCount: 35,
    baseCrowd: 86,
    rainSensitivity: -3.2,
    isPopularSpot: true
  },

  // ── 4. 성동·광진·동대문·중랑 (동북 수변권) ──
  {
    id: 'bike-seoul-forest',
    name: '따릉이: 서울숲역 3번출구·서울숲입구',
    stationNo: '502',
    district: '성동구',
    coords: [127.0442, 37.5435],
    lineInfo: '거치대 40대 (서울숲 생태공원)',
    rackCount: 40,
    baseCrowd: 93,
    rainSensitivity: -3.4,
    isPopularSpot: true
  },
  {
    id: 'bike-ttukseom-resort',
    name: '따릉이: 뚝섬한강공원 자벌레앞',
    stationNo: '505',
    district: '광진구',
    coords: [127.0672, 37.5295],
    lineInfo: '거치대 50대 (뚝섬 한강 라이딩)',
    rackCount: 50,
    baseCrowd: 96,
    rainSensitivity: -3.7,
    isPopularSpot: true
  },
  {
    id: 'bike-konkuk-exit2',
    name: '따릉이: 건대입구역 2번출구앞',
    stationNo: '512',
    district: '광진구',
    coords: [127.0715, 37.5408],
    lineInfo: '거치대 25대 (일감호 연결)',
    rackCount: 25,
    baseCrowd: 84,
    rainSensitivity: -2.8
  },
  {
    id: 'bike-wangsimni-exit6',
    name: '따릉이: 왕십리역 6번출구(한양대)',
    stationNo: '528',
    district: '성동구',
    coords: [127.0378, 37.5608],
    lineInfo: '거치대 30대 (대학가 연결)',
    rackCount: 30,
    baseCrowd: 80,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-cheonggye-yongdu',
    name: '따릉이: 용두역 4번출구(청계천)',
    stationNo: '614',
    district: '동대문구',
    coords: [127.0382, 37.5742],
    lineInfo: '거치대 20대 (청계천 하류 코스)',
    rackCount: 20,
    baseCrowd: 73,
    rainSensitivity: -2.9
  },
  {
    id: 'bike-jungnang-stream',
    name: '따릉이: 중랑천 장미공원 입구',
    stationNo: '1420',
    district: '중랑구',
    coords: [127.0815, 37.6082],
    lineInfo: '거치대 30대 (중랑천 둔치길 연결)',
    rackCount: 30,
    baseCrowd: 82,
    rainSensitivity: -3.1,
    isPopularSpot: true
  },

  // ── 5. 성북·강북·도봉·노원 (북부권) ──
  {
    id: 'bike-korea-univ',
    name: '따릉이: 안암역 3번출구(고려대정문)',
    stationNo: '1308',
    district: '성북구',
    coords: [127.0305, 37.5858],
    lineInfo: '거치대 25대 (고대 캠퍼스)',
    rackCount: 25,
    baseCrowd: 81,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-sungshin-exit1',
    name: '따릉이: 성신여대입구역 1번출구',
    stationNo: '1322',
    district: '성북구',
    coords: [127.0182, 37.5932],
    lineInfo: '거치대 20대 (성북천 자전거길)',
    rackCount: 20,
    baseCrowd: 76,
    rainSensitivity: -2.5
  },
  {
    id: 'bike-bukseoul-dream',
    name: '따릉이: 북서울꿈의숲 동문광장',
    stationNo: '1504',
    district: '강북구',
    coords: [127.0415, 37.6205],
    lineInfo: '거치대 35대 (대형 공원 순환)',
    rackCount: 35,
    baseCrowd: 87,
    rainSensitivity: -3.3,
    isPopularSpot: true
  },
  {
    id: 'bike-suyu-exit4',
    name: '따릉이: 수유역 4번출구(강북구청)',
    stationNo: '1518',
    district: '강북구',
    coords: [127.0262, 37.6368],
    lineInfo: '거치대 25대 (우이천 자전거길)',
    rackCount: 25,
    baseCrowd: 78,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-changdong-exit1',
    name: '따릉이: 창동역 1번출구 광장',
    stationNo: '1610',
    district: '도봉구',
    coords: [127.0485, 37.6538],
    lineInfo: '거치대 30대 (중랑천 합류로)',
    rackCount: 30,
    baseCrowd: 82,
    rainSensitivity: -2.8
  },
  {
    id: 'bike-nowon-exit7',
    name: '따릉이: 노원역 7번출구앞',
    stationNo: '1705',
    district: '노원구',
    coords: [127.0605, 37.6545],
    lineInfo: '거치대 30대 (당현천 자전거길)',
    rackCount: 30,
    baseCrowd: 84,
    rainSensitivity: -2.9,
    isPopularSpot: true
  },
  {
    id: 'bike-seoul-tech',
    name: '따릉이: 서울과기대 정문앞',
    stationNo: '1735',
    district: '노원구',
    coords: [127.0782, 37.6322],
    lineInfo: '거치대 25대 (경춘선숲길 연결)',
    rackCount: 25,
    baseCrowd: 80,
    rainSensitivity: -2.7
  },

  // ── 6. 구로·금천·관악·동작·양천·강서 (서남 공단·주거권) ──
  {
    id: 'bike-sindorim-exit1',
    name: '따릉이: 신도림역 1번출구(디큐브시티)',
    stationNo: '1905',
    district: '구로구',
    coords: [126.8922, 37.5092],
    lineInfo: '거치대 35대 (도림천 자전거길 연결)',
    rackCount: 35,
    baseCrowd: 86,
    rainSensitivity: -3.0,
    isPopularSpot: true
  },
  {
    id: 'bike-guro-dc-exit3',
    name: '따릉이: 구로디지털단지역 3번출구',
    stationNo: '1918',
    district: '구로구',
    coords: [126.9008, 37.4845],
    lineInfo: '거치대 30대 (G밸리 통근 코스)',
    rackCount: 30,
    baseCrowd: 88,
    rainSensitivity: -2.8,
    isPopularSpot: true
  },
  {
    id: 'bike-gasan-exit7',
    name: '따릉이: 가산디지털단지역 7번출구',
    stationNo: '2004',
    district: '금천구',
    coords: [126.8835, 37.4808],
    lineInfo: '거치대 30대 (안양천 자전거길 방면)',
    rackCount: 30,
    baseCrowd: 85,
    rainSensitivity: -2.9,
    isPopularSpot: true
  },
  {
    id: 'bike-anyang-stream-gc',
    name: '따릉이: 금천구청역 안양천자전거길',
    stationNo: '2015',
    district: '금천구',
    coords: [126.8925, 37.4595],
    lineInfo: '거치대 25대 (안양천 장거리 라이딩)',
    rackCount: 25,
    baseCrowd: 82,
    rainSensitivity: -3.3
  },
  {
    id: 'bike-dorim-sillim',
    name: '따릉이: 신림역 5번출구(도림천변)',
    stationNo: '2105',
    district: '관악구',
    coords: [126.9282, 37.4835],
    lineInfo: '거치대 35대 (도림천 자전거전용도로)',
    rackCount: 35,
    baseCrowd: 89,
    rainSensitivity: -3.2,
    isPopularSpot: true
  },
  {
    id: 'bike-snu-station-exit3',
    name: '따릉이: 서울대입구역 3번출구',
    stationNo: '2118',
    district: '관악구',
    coords: [126.9532, 37.4805],
    lineInfo: '거치대 25대 (관악산 방면 통학)',
    rackCount: 25,
    baseCrowd: 81,
    rainSensitivity: -2.6
  },
  {
    id: 'bike-boramae-park',
    name: '따릉이: 보라매공원 동문입구',
    stationNo: '2055',
    district: '동작구',
    coords: [126.9245, 37.4935],
    lineInfo: '거치대 30대 (공원 순환트랙)',
    rackCount: 30,
    baseCrowd: 85,
    rainSensitivity: -3.2,
    isPopularSpot: true
  },
  {
    id: 'bike-noryangjin-exit1',
    name: '따릉이: 노량진역 1번출구앞',
    stationNo: '2001',
    district: '동작구',
    coords: [126.9415, 37.5142],
    lineInfo: '거치대 20대 (수산시장 연결)',
    rackCount: 20,
    baseCrowd: 77,
    rainSensitivity: -2.5
  },
  {
    id: 'bike-anyang-stream-omok',
    name: '따릉이: 오목교역 5번출구(안양천변)',
    stationNo: '702',
    district: '양천구',
    coords: [126.8762, 37.5252],
    lineInfo: '거치대 30대 (안양천 둔치로)',
    rackCount: 30,
    baseCrowd: 83,
    rainSensitivity: -3.1,
    isPopularSpot: true
  },
  {
    id: 'bike-seoul-botanic-park',
    name: '따릉이: 서울식물원 온실입구(마곡나루)',
    stationNo: '1125',
    district: '강서구',
    coords: [126.8325, 37.5685],
    lineInfo: '거치대 40대 (식물원 호수공원)',
    rackCount: 40,
    baseCrowd: 91,
    rainSensitivity: -3.5,
    isPopularSpot: true
  },
  {
    id: 'bike-hangang-gangseo',
    name: '따릉이: 강서한강공원 방화대교남단',
    stationNo: '1140',
    district: '강서구',
    coords: [126.8145, 37.5895],
    lineInfo: '거치대 30대 (아라뱃길 라이딩 연계)',
    rackCount: 30,
    baseCrowd: 84,
    rainSensitivity: -3.4
  }
]

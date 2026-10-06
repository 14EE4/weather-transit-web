// 서울시 25개 자치구 및 수도권 주요 관문 핵심 버스 정류소 / 환승센터 마스터 데이터
export interface BusStop {
  id: string
  name: string
  district: string
  coords: [number, number] // [lng, lat]
  lineInfo: string
  stId?: string // 서울시 버스정류소 고유 ID (공공 API 연동용)
  arsId?: string // 정류소 번호 (5자리)
  baseCrowd: number // 기본 혼잡도 (0~100)
  rainSensitivity: number
  isHub?: boolean // 대형 환승센터 여부
}

export const BUS_STOPS: BusStop[] = [
  // ── 1. 도심권 (종로구, 중구, 용산구) ──
  {
    id: 'bus-seoul-tc',
    name: '서울역버스환승센터',
    district: '중구',
    coords: [126.9723, 37.5562],
    lineInfo: '150, 402, 503, 702, M4108 등',
    stId: '101000003',
    arsId: '02003',
    baseCrowd: 82,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-jongno3ga',
    name: '종로3가·탑골공원(중앙차로)',
    district: '종로구',
    coords: [126.9912, 37.5702],
    lineInfo: '101, 103, 143, 260, 370, 720 등',
    stId: '100000021',
    arsId: '01015',
    baseCrowd: 74,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-gwanghwamun',
    name: '광화문·세종문화회관',
    district: '종로구',
    coords: [126.9765, 37.5718],
    lineInfo: '109, 606, 704, 1002, 7900 등',
    stId: '100000018',
    arsId: '01014',
    baseCrowd: 76,
    rainSensitivity: 1.3
  },
  {
    id: 'bus-dongdaemun',
    name: '동대문·흥인지문(중앙차로)',
    district: '종로구',
    coords: [127.0098, 37.5712],
    lineInfo: '105, 144, 261, 301, 420, 2233 등',
    stId: '100000035',
    arsId: '01024',
    baseCrowd: 72,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-myeongdong',
    name: '명동국민은행앞·을지로입구',
    district: '중구',
    coords: [126.9852, 37.5635],
    lineInfo: '100, 104, 152, 202, 408, 507 등',
    stId: '101000052',
    arsId: '02143',
    baseCrowd: 78,
    rainSensitivity: 1.3
  },
  {
    id: 'bus-chungmuro',
    name: '대한극장앞·충무로역',
    district: '중구',
    coords: [126.9942, 37.5612],
    lineInfo: '104, 140, 463, 507, 7011 등',
    stId: '101000062',
    arsId: '02153',
    baseCrowd: 68,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-yongsan-st',
    name: '용산역광장앞',
    district: '용산구',
    coords: [126.9648, 37.5298],
    lineInfo: '400, 502, 505, 0411, 2016 등',
    stId: '102000080',
    arsId: '03165',
    baseCrowd: 75,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-samgakji',
    name: '삼각지역(중앙차로)',
    district: '용산구',
    coords: [126.9732, 37.5348],
    lineInfo: '150, 151, 152, 500, 504, 750A 등',
    stId: '102000008',
    arsId: '03006',
    baseCrowd: 66,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-itaewon',
    name: '이태원역·해밀톤호텔',
    district: '용산구',
    coords: [126.9945, 37.5345],
    lineInfo: '110A, 400, 405, 421, 0411 등',
    stId: '102000095',
    arsId: '03198',
    baseCrowd: 71,
    rainSensitivity: 1.2
  },

  // ── 2. 동남권 (강남구, 서초구, 송파구, 강동구) ──
  {
    id: 'bus-gn-center',
    name: '강남역(중앙차로)',
    district: '강남구',
    coords: [127.0282, 37.4988],
    lineInfo: '140, 400, 420, 470, 741, 9408 등',
    stId: '121000010',
    arsId: '22010',
    baseCrowd: 85,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-sinnonhyeon',
    name: '신논현역·교보타워사거리',
    district: '강남구',
    coords: [127.0252, 37.5045],
    lineInfo: '144, 360, 421, 6411, 9711 등',
    stId: '121000013',
    arsId: '22012',
    baseCrowd: 79,
    rainSensitivity: 1.3
  },
  {
    id: 'bus-samseong',
    name: '무역센터(삼성역)',
    district: '강남구',
    coords: [127.0601, 37.5097],
    lineInfo: '143, 301, 3412, 3425, 9407 등',
    stId: '122000058',
    arsId: '23198',
    baseCrowd: 76,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-suseo',
    name: '수서역·SRT고속철도환승',
    district: '강남구',
    coords: [127.1025, 37.4875],
    lineInfo: '401, 402, 3413, 3426, 강남06 등',
    stId: '122000287',
    arsId: '23412',
    baseCrowd: 73,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-express-bus-term',
    name: '고속터미널(중앙차로)',
    district: '서초구',
    coords: [127.0051, 37.5055],
    lineInfo: '142, 143, 360, 401, 462, 640 등',
    stId: '121000025',
    arsId: '22020',
    baseCrowd: 84,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-yangjae',
    name: '양재역·말죽거리(중앙차로)',
    district: '서초구',
    coords: [127.0345, 37.4842],
    lineInfo: '140, 400, 452, 470, 9404, G3900 등',
    stId: '121000006',
    arsId: '22004',
    baseCrowd: 81,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-sadang-sc',
    name: '사당역(방배동방면)',
    district: '서초구',
    coords: [126.9816, 37.4765],
    lineInfo: '4435, 5524, 7007-1, 7770, 8155 등',
    stId: '121000174',
    arsId: '22245',
    baseCrowd: 83,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-jamsil-tc',
    name: '잠실역광역환승센터',
    district: '송파구',
    coords: [127.1002, 37.5133],
    lineInfo: '30-1, 1000, 1115-6, M2316, 8001 등',
    stId: '123000600',
    arsId: '24050',
    baseCrowd: 88,
    rainSensitivity: 1.4,
    isHub: true
  },
  {
    id: 'bus-garak-market',
    name: '가락시장역(중앙차로)',
    district: '송파구',
    coords: [127.1182, 37.4925],
    lineInfo: '301, 302, 303, 360, 9403, 1009 등',
    stId: '123000014',
    arsId: '24010',
    baseCrowd: 71,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-cheonho',
    name: '천호역·현대백화점(중앙차로)',
    district: '강동구',
    coords: [127.1238, 37.5385],
    lineInfo: '130, 340, 370, 3411, 9301 등',
    stId: '124000015',
    arsId: '25010',
    baseCrowd: 80,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-gangdong-st',
    name: '강동역(중앙차로)',
    district: '강동구',
    coords: [127.1325, 37.5358],
    lineInfo: '130, 342, 370, 3316, 112-1 등',
    stId: '124000018',
    arsId: '25012',
    baseCrowd: 69,
    rainSensitivity: 1.2
  },

  // ── 3. 서남권 (영등포구, 마포구, 구로구, 금천구, 관악구, 동작구, 양천구, 강서구) ──
  {
    id: 'bus-yeouido-tc',
    name: '여의도환승센터',
    district: '영등포구',
    coords: [126.9255, 37.5248],
    lineInfo: '160, 260, 600, 5012, 8600, G7625 등',
    stId: '118000045',
    arsId: '19007',
    baseCrowd: 84,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-ydp-station',
    name: '영등포역(중앙차로)',
    district: '영등포구',
    coords: [126.9075, 37.5158],
    lineInfo: '160, 260, 503, 600, 6512, 88 등',
    stId: '118000008',
    arsId: '19008',
    baseCrowd: 81,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-dangsan-st',
    name: '당산역광역환승정류장',
    district: '영등포구',
    coords: [126.9025, 37.5348],
    lineInfo: '603, 605, 5714, 6514, 70-3, G6001 등',
    stId: '118000620',
    arsId: '19018',
    baseCrowd: 83,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-hongdae',
    name: '홍대입구역(중앙차로)',
    district: '마포구',
    coords: [126.9238, 37.5572],
    lineInfo: '271, 602, 603, 604, 7612, 7711 등',
    stId: '113000015',
    arsId: '14015',
    baseCrowd: 86,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-hapjeong',
    name: '합정역(중앙차로)',
    district: '마포구',
    coords: [126.9135, 37.5495],
    lineInfo: '271, 603, 760, 5714, 7011, 200 등',
    stId: '113000012',
    arsId: '14013',
    baseCrowd: 78,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-gongdeok',
    name: '공덕역(중앙차로)',
    district: '마포구',
    coords: [126.9515, 37.5442],
    lineInfo: '160, 260, 600, 740, 7013A, 7613 등',
    stId: '113000002',
    arsId: '14002',
    baseCrowd: 77,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-guro-dc',
    name: '구로디지털단지역환승센터',
    district: '구로구',
    coords: [126.9015, 37.4852],
    lineInfo: '150, 505, 5531, 5536, 5616, 900 등',
    stId: '116000010',
    arsId: '17011',
    baseCrowd: 85,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-sindorim',
    name: '신도림역(중앙차로)',
    district: '구로구',
    coords: [126.8912, 37.5088],
    lineInfo: '160, 503, 600, 670, 5615, 6512 등',
    stId: '116000001',
    arsId: '17001',
    baseCrowd: 82,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-gasan-dc',
    name: '가산디지털단지역사거리',
    district: '금천구',
    coords: [126.8828, 37.4815],
    lineInfo: '503, 504, 571, 652, 5537, 5714 등',
    stId: '117000105',
    arsId: '18115',
    baseCrowd: 79,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-geumcheon-gc',
    name: '금천구청·금천경찰서',
    district: '금천구',
    coords: [126.8945, 37.4602],
    lineInfo: '150, 505, 5531, 5538, 5617, 900 등',
    stId: '117000008',
    arsId: '18008',
    baseCrowd: 68,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-sillim',
    name: '신림역·순대타운',
    district: '관악구',
    coords: [126.9295, 37.4842],
    lineInfo: '152, 504, 5516, 5522, 6514, 관악05 등',
    stId: '120000085',
    arsId: '21125',
    baseCrowd: 84,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-snu-station',
    name: '서울대입구역(중앙차로)',
    district: '관악구',
    coords: [126.9525, 37.4812],
    lineInfo: '501, 506, 5511, 5515, 6512, 6515 등',
    stId: '120000005',
    arsId: '21006',
    baseCrowd: 78,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-noryangjin',
    name: '노량진역(중앙차로)',
    district: '동작구',
    coords: [126.9425, 37.5135],
    lineInfo: '150, 152, 500, 504, 605, 6411 등',
    stId: '119000012',
    arsId: '20011',
    baseCrowd: 80,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-mokdong',
    name: '목동역·목동오거리',
    district: '양천구',
    coords: [126.8648, 37.5262],
    lineInfo: '571, 602, 640, 6211, 6614, 6628 등',
    stId: '114000125',
    arsId: '15152',
    baseCrowd: 74,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-omokgyo',
    name: '오목교역·현대백화점',
    district: '양천구',
    coords: [126.8752, 37.5245],
    lineInfo: '571, 603, 640, 650, 5012, 6624 등',
    stId: '114000130',
    arsId: '15160',
    baseCrowd: 73,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-balsan',
    name: '발산역(중앙차로)',
    district: '강서구',
    coords: [126.8375, 37.5585],
    lineInfo: '601, 605, 654, 6632, 6712, 3000 등',
    stId: '115000015',
    arsId: '16012',
    baseCrowd: 75,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-hwagok',
    name: '화곡역·화곡시장',
    district: '강서구',
    coords: [126.8405, 37.5415],
    lineInfo: '604, 606, 652, 653, 6627, 70-3 등',
    stId: '115000108',
    arsId: '16145',
    baseCrowd: 76,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-gimpo-airport',
    name: '김포공항국내선환승센터',
    district: '강서구',
    coords: [126.8015, 37.5585],
    lineInfo: '601, 605, 6632, 3, 20, 60-3, 6014 등',
    stId: '115000405',
    arsId: '16920',
    baseCrowd: 82,
    rainSensitivity: 1.3,
    isHub: true
  },

  // ── 4. 동북권 (성동구, 광진구, 동대문구, 중랑구, 성북구, 강북구, 도봉구, 노원구) ──
  {
    id: 'bus-wangsimni-tc',
    name: '왕십리역환승센터',
    district: '성동구',
    coords: [127.0368, 37.5615],
    lineInfo: '110B, 141, 145, 148, 421, 2014 등',
    stId: '103000112',
    arsId: '04140',
    baseCrowd: 78,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-seongsu',
    name: '성수역·카페거리입구',
    district: '성동구',
    coords: [127.0558, 37.5445],
    lineInfo: '2016, 2224, 2413, 성동10, 성동13 등',
    stId: '103000155',
    arsId: '04215',
    baseCrowd: 73,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-konkuk',
    name: '건대입구역사거리',
    district: '광진구',
    coords: [127.0705, 37.5405],
    lineInfo: '240, 721, 2016, 2222, 3220, 4212 등',
    stId: '104000142',
    arsId: '05145',
    baseCrowd: 81,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-gangbyeon-tc',
    name: '강변역환승센터(동서울터미널)',
    district: '광진구',
    coords: [127.0945, 37.5352],
    lineInfo: '1, 1-1, 9, 13-2, 112, 1115-2 등',
    stId: '104000305',
    arsId: '05280',
    baseCrowd: 85,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-cheongnyangni-tc',
    name: '청량리역환승센터',
    district: '동대문구',
    coords: [127.0452, 37.5802],
    lineInfo: '105, 120, 201, 260, 270, 720, 3200 등',
    stId: '105000018',
    arsId: '06018',
    baseCrowd: 86,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-hoegi',
    name: '회기역앞·경희대입구',
    district: '동대문구',
    coords: [127.0575, 37.5898],
    lineInfo: '120, 147, 261, 273, 1222, 동대문01 등',
    stId: '105000180',
    arsId: '06215',
    baseCrowd: 74,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-sangbong',
    name: '상봉역·중랑우체국(중앙차로)',
    district: '중랑구',
    coords: [127.0855, 37.5962],
    lineInfo: '201, 260, 270, 272, 2114, 2235 등',
    stId: '106000012',
    arsId: '07010',
    baseCrowd: 76,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-sungshin',
    name: '성신여대입구(중앙차로)',
    district: '성북구',
    coords: [127.0175, 37.5925],
    lineInfo: '100, 102, 104, 106, 140, 150, 151 등',
    stId: '107000015',
    arsId: '08008',
    baseCrowd: 77,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-gireum',
    name: '길음역(중앙차로)',
    district: '성북구',
    coords: [127.0245, 37.6032],
    lineInfo: '106, 140, 143, 150, 153, 160, 171 등',
    stId: '107000010',
    arsId: '08004',
    baseCrowd: 79,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-suyu',
    name: '수유역·강북구청(중앙차로)',
    district: '강북구',
    coords: [127.0255, 37.6375],
    lineInfo: '101, 106, 107, 108, 120, 140, 150, 160 등',
    stId: '108000012',
    arsId: '09010',
    baseCrowd: 83,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-mia-cross',
    name: '미아사거리역(중앙차로)',
    district: '강북구',
    coords: [127.0305, 37.6135],
    lineInfo: '101, 102, 106, 107, 120, 130, 140, 150 등',
    stId: '108000004',
    arsId: '09004',
    baseCrowd: 82,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-dobongsan-tc',
    name: '도봉산역광역환승센터',
    district: '도봉구',
    coords: [127.0445, 37.6895],
    lineInfo: '106, 107, 108, 1151, 1154, 72-1, 118 등',
    stId: '109000002',
    arsId: '10002',
    baseCrowd: 80,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-ssangmun',
    name: '쌍문역(중앙차로)',
    district: '도봉구',
    coords: [127.0345, 37.6482],
    lineInfo: '101, 106, 107, 108, 130, 140, 150, 160 등',
    stId: '109000010',
    arsId: '10008',
    baseCrowd: 77,
    rainSensitivity: 1.25
  },
  {
    id: 'bus-nowon',
    name: '노원역·롯데백화점(중앙차로)',
    district: '노원구',
    coords: [127.0615, 37.6552],
    lineInfo: '102, 105, 146, 1129, 1137, 1144 등',
    stId: '110000018',
    arsId: '11012',
    baseCrowd: 81,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-taereung',
    name: '태릉입구역(중앙차로)',
    district: '노원구',
    coords: [127.0755, 37.6182],
    lineInfo: '105, 146, 1122, 1132, 1224, 1227 등',
    stId: '110000005',
    arsId: '11004',
    baseCrowd: 75,
    rainSensitivity: 1.25
  },

  // ── 5. 서북권 (은평구, 서대문구) ──
  {
    id: 'bus-yeonsinnae',
    name: '연신내역·로데오거리(중앙차로)',
    district: '은평구',
    coords: [126.9205, 37.6192],
    lineInfo: '471, 701, 703, 704, 720, 7715, 9709 등',
    stId: '111000010',
    arsId: '12010',
    baseCrowd: 82,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-bulgwang',
    name: '불광역·시외버스터미널(중앙차로)',
    district: '은평구',
    coords: [126.9298, 37.6105],
    lineInfo: '701, 703, 704, 720, 7720, 7734 등',
    stId: '111000005',
    arsId: '12005',
    baseCrowd: 78,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-gusan-cross',
    name: '구산동사거리',
    district: '은평구',
    coords: [126.9082, 37.6112],
    lineInfo: '753, 7613, 8774, 은평02 등',
    stId: '111000299',
    arsId: '12299',
    baseCrowd: 65,
    rainSensitivity: 1.2
  },
  {
    id: 'bus-yonsei',
    name: '연세대앞(중앙차로)',
    district: '서대문구',
    coords: [126.9365, 37.5598],
    lineInfo: '153, 272, 606, 708, 7720, 7737 등',
    stId: '112000018',
    arsId: '13014',
    baseCrowd: 81,
    rainSensitivity: 1.25,
    isHub: true
  },
  {
    id: 'bus-sinchon-5',
    name: '신촌오거리·현대백화점(중앙차로)',
    district: '서대문구',
    coords: [126.9368, 37.5552],
    lineInfo: '270, 271, 273, 602, 603, 721, 5714 등',
    stId: '112000012',
    arsId: '13012',
    baseCrowd: 83,
    rainSensitivity: 1.3,
    isHub: true
  },

  // ── 6. 수도권 주요 광역 관문 (판교, 부평, 수원) ──
  {
    id: 'bus-pangyo-tc',
    name: '판교역환승센터',
    district: '성남시',
    coords: [127.1115, 37.3948],
    lineInfo: '390, 4000, 9005, 9300, 9507, M4102 등',
    stId: '206000540',
    arsId: '07490',
    baseCrowd: 85,
    rainSensitivity: 1.35,
    isHub: true
  },
  {
    id: 'bus-bupyeong-st',
    name: '부평역광장·환승센터',
    district: '인천시',
    coords: [126.7245, 37.4895],
    lineInfo: '12, 30, 45, 88, 551, 9500 등',
    stId: '166000120',
    arsId: '40120',
    baseCrowd: 82,
    rainSensitivity: 1.3,
    isHub: true
  },
  {
    id: 'bus-suwon-tc',
    name: '수원역환승센터',
    district: '수원시',
    coords: [126.9995, 37.2662],
    lineInfo: '11-1, 13, 88, 777, 2007, 7770, 8409 등',
    stId: '202000050',
    arsId: '03015',
    baseCrowd: 86,
    rainSensitivity: 1.35,
    isHub: true
  }
]

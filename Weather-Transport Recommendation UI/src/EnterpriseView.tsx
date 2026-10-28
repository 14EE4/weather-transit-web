import React, { useState, useEffect, useMemo } from 'react';

export interface B2BDistrictItem {
  district: string;
  district_code: number;
  bike_demand: number;
  bike_baseline: number;
  bike_delta_pct: number;
  bike_status: 'SURPLUS' | 'DEFICIT' | 'STABLE';
  bike_action: 'RECALL' | 'DEPLOY' | 'MAINTAIN';
  bike_rebalance_qty: number;
  bus_demand: number;
  bus_baseline: number;
  bus_delta_pct: number;
  bus_status: 'CROWDED' | 'NORMAL' | 'LIGHT';
  bus_recommended_trips: number;
  subway_demand: number;
  subway_baseline: number;
  subway_delta_pct: number;
  infra: {
    bike_racks: number;
    bus_stops: number;
    subway_stations: number;
  };
  urgency: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  actionable_guidance: string;
}

export interface B2BResponse {
  status: string;
  latency_ms: number;
  weather_condition: {
    rain_mm: number;
    temp: number;
    hour: number;
    is_raining: boolean;
  };
  total_bike_surplus_qty: number;
  total_bike_deficit_qty: number;
  total_bus_extra_trips: number;
  top_recall_districts: Array<{ district: string; qty: number; delta_pct: number; urgency: string }>;
  top_deploy_districts: Array<{ district: string; qty: number; delta_pct: number; urgency: string }>;
  district_rebalance_list: B2BDistrictItem[];
}

interface EnterpriseViewProps {
  apiBaseUrl: string;
}

export const EnterpriseView: React.FC<EnterpriseViewProps> = ({ apiBaseUrl }) => {
  // 제어 상태
  const [hour, setHour] = useState<number>(new Date().getHours());
  const [rainMm, setRainMm] = useState<number>(0.0);
  const [temp, setTemp] = useState<number>(18.0);
  const [useLiveWeather, setUseLiveWeather] = useState<boolean>(true);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'SURPLUS' | 'DEFICIT' | 'STABLE'>('ALL');
  const [searchKeyword, setSearchKeyword] = useState<string>('');

  // 데이터 상태
  const [data, setData] = useState<B2BResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchB2BAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/b2b/fleet-rebalance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hour,
          rain_mm: rainMm,
          temp,
          use_live_weather: useLiveWeather,
        }),
      });
      if (!res.ok) {
        throw new Error(`서버 응답 오류 (Status: ${res.status})`);
      }
      const json: B2BResponse = await res.json();
      setData(json);
      if (useLiveWeather && json.weather_condition) {
        setRainMm(json.weather_condition.rain_mm);
        setTemp(json.weather_condition.temp);
      }
    } catch (err: any) {
      console.error('B2B API Error:', err);
      setError(err.message || '데이터를 불러오는 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchB2BAnalysis();
  }, [hour, useLiveWeather]);

  // 필터링된 자치구 목록
  const filteredList = useMemo(() => {
    if (!data?.district_rebalance_list) return [];
    return data.district_rebalance_list.filter((item) => {
      const matchStatus = filterStatus === 'ALL' || item.bike_status === filterStatus;
      const matchSearch = item.district.includes(searchKeyword.trim());
      return matchStatus && matchSearch;
    });
  }, [data, filterStatus, searchKeyword]);

  // CSV 다운로드 함수
  const handleExportCSV = () => {
    if (!data?.district_rebalance_list) return;
    const headers = [
      '자치구',
      '시간대',
      '강수량(mm)',
      '따릉이예상수요',
      '따릉이기준수요',
      '따릉이증감율(%)',
      '따릉이수급상태',
      '권장조치',
      '권장조정수량(대)',
      '버스증차권고(회)',
      '긴급도',
      '운영가이드',
    ];
    const rows = data.district_rebalance_list.map((d) => [
      d.district,
      `${data.weather_condition.hour}시`,
      data.weather_condition.rain_mm,
      d.bike_demand,
      d.bike_baseline,
      `${d.bike_delta_pct}%`,
      d.bike_status,
      d.bike_action,
      d.bike_rebalance_qty,
      d.bus_recommended_trips,
      d.urgency,
      `"${d.actionable_guidance.replace(/"/g, '""')}"`,
    ]);
    const csvContent =
      'data:text/csv;charset=utf-8,\uFEFF' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `b2b_fleet_rebalance_${data.weather_condition.hour}h.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 32px 80px' }}>
      {/* ── 헤더 타이틀 ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 28 }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px', borderRadius: 20, background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.3)', marginBottom: 10 }}>
            <span style={{ fontSize: 13 }}>🏢</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', letterSpacing: '0.05em' }}>
              ENTERPRISE FLEET FORECAST & REBALANCING
            </span>
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: '#F0F6FF', margin: 0, letterSpacing: '-0.5px' }}>
            기업용 교통수단 수요 예측 및 재배치 관제
          </h1>
          <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.5)', margin: '6px 0 0', lineHeight: 1.5 }}>
            팀 <strong style={{ color: '#38BDF8' }}>선견지명</strong>의 32차원 AI 모델을 기반으로 기상 변화에 따른 모빌리티 잉여/부족을 선제 진단하고 최적 재배치 수량을 산출합니다.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={handleExportCSV}
            disabled={!data}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 18px', borderRadius: 10,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
              color: '#F0F6FF', fontSize: 13, fontWeight: 600, cursor: data ? 'pointer' : 'not-allowed',
              transition: 'all 0.15s ease'
            }}
          >
            <span>📥</span> CSV 리포트 다운로드
          </button>
          <button
            onClick={fetchB2BAnalysis}
            disabled={loading}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 20px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0284C7, #0EA5E9)', border: 'none',
              color: '#FFFFFF', fontSize: 13, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 14px rgba(14,165,233,0.3)'
            }}
          >
            <span>{loading ? '⏳' : '🔄'}</span> {loading ? '분석 연산 중...' : '재배치 지표 산출'}
          </button>
        </div>
      </div>

      {/* ── 컨트롤러 패널 ── */}
      <div style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, padding: '22px 28px', marginBottom: 28 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20, alignItems: 'center' }}>
          {/* 실시간 기상 스위치 */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)', marginBottom: 8 }}>
              기상 데이터 연동 모드
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setUseLiveWeather(true)}
                style={{
                  flex: 1, padding: '8px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  background: useLiveWeather ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.05)',
                  border: useLiveWeather ? '1px solid #38BDF8' : '1px solid rgba(255,255,255,0.1)',
                  color: useLiveWeather ? '#38BDF8' : 'rgba(255,255,255,0.5)',
                  cursor: 'pointer'
                }}
              >
                📡 기상청 실시간 실황
              </button>
              <button
                onClick={() => setUseLiveWeather(false)}
                style={{
                  flex: 1, padding: '8px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  background: !useLiveWeather ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.05)',
                  border: !useLiveWeather ? '1px solid #38BDF8' : '1px solid rgba(255,255,255,0.1)',
                  color: !useLiveWeather ? '#38BDF8' : 'rgba(255,255,255,0.5)',
                  cursor: 'pointer'
                }}
              >
                🧪 가상 기상 시뮬레이션
              </button>
            </div>
          </div>

          {/* 시간대 선택 */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>관제 대상 시간대</label>
              <span style={{ fontSize: 12, fontWeight: 800, color: '#38BDF8' }}>{hour}:00</span>
            </div>
            <input
              type="range"
              min="0"
              max="23"
              value={hour}
              onChange={(e) => setHour(parseInt(e.target.value, 10))}
              style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 4 }}>
              <span>00시(심야)</span>
              <span>08시(출근)</span>
              <span>12시(점심)</span>
              <span>18시(퇴근)</span>
              <span>23시</span>
            </div>
          </div>

          {/* 강수량 조절 (시뮬레이션 모드 시 활성화) */}
          <div style={{ opacity: useLiveWeather ? 0.5 : 1.0, pointerEvents: useLiveWeather ? 'none' : 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>가상 강수량 (Rain)</label>
              <span style={{ fontSize: 12, fontWeight: 800, color: rainMm > 0 ? '#38BDF8' : '#94A3B8' }}>{rainMm.toFixed(1)} mm/h</span>
            </div>
            <input
              type="range"
              min="0"
              max="15"
              step="0.5"
              value={rainMm}
              onChange={(e) => setRainMm(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 4 }}>
              <span>맑음(0)</span>
              <span>소우(2)</span>
              <span>보통(5)</span>
              <span>폭우(10+)</span>
            </div>
          </div>

          {/* 기온 조절 */}
          <div style={{ opacity: useLiveWeather ? 0.5 : 1.0, pointerEvents: useLiveWeather ? 'none' : 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>가상 기온 (Temp)</label>
              <span style={{ fontSize: 12, fontWeight: 800, color: '#38BDF8' }}>{temp.toFixed(1)} °C</span>
            </div>
            <input
              type="range"
              min="-10"
              max="35"
              step="1"
              value={temp}
              onChange={(e) => setTemp(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer' }}
            />
          </div>
        </div>
      </div>

      {/* ── 에러 알림 ── */}
      {error && (
        <div style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 12, padding: '16px 20px', color: '#FCA5A5', marginBottom: 24, fontSize: 13 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── KPI 요약 카드 4종 ── */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 28 }}>
          {/* 카드 1: 따릉이 유휴 회수 권고 */}
          <div style={{ background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)' }}>따릉이 유휴 잉여 회수 권고</span>
              <span style={{ fontSize: 18 }}>🚲</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, color: data.total_bike_surplus_qty > 0 ? '#38BDF8' : '#94A3B8' }}>
              {data.total_bike_surplus_qty.toLocaleString()} <span style={{ fontSize: 15, fontWeight: 600 }}>대</span>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 6 }}>
              {data.weather_condition.is_raining ? '우천 침수 위험지 및 유휴 거점 선제 회수' : '기상 양호로 수급 안정적'}
            </div>
          </div>

          {/* 카드 2: 따릉이 거점 추가 배치 */}
          <div style={{ background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)' }}>따릉이 수요 급증 배치 권고</span>
              <span style={{ fontSize: 18 }}>⚡</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, color: data.total_bike_deficit_qty > 0 ? '#F59E0B' : '#94A3B8' }}>
              {data.total_bike_deficit_qty.toLocaleString()} <span style={{ fontSize: 15, fontWeight: 600 }}>대</span>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 6 }}>
              주요 환승 거점역 및 오피스 권역 조기 품절 방지
            </div>
          </div>

          {/* 카드 3: 버스 배차 증차 권고 */}
          <div style={{ background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)' }}>시내버스 집중 배차 권고</span>
              <span style={{ fontSize: 18 }}>🚌</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, color: data.total_bus_extra_trips > 0 ? '#10B981' : '#94A3B8' }}>
              +{data.total_bus_extra_trips} <span style={{ fontSize: 15, fontWeight: 600 }}>회 증차</span>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 6 }}>
              우천 전이 승차객 밀집 노선 배차 간격 단축
            </div>
          </div>

          {/* 카드 4: AI 추론 레이턴시 */}
          <div style={{ background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)' }}>25개 구 일괄 AI 추론 지연시간</span>
              <span style={{ fontSize: 18 }}>⏱️</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, color: '#38BDF8' }}>
              {data.latency_ms} <span style={{ fontSize: 15, fontWeight: 600 }}>ms</span>
            </div>
            <div style={{ fontSize: 11, color: '#34D399', marginTop: 6 }}>
              ONNX Runtime SLA(50ms) 대비 10배 초고속 연산
            </div>
          </div>
        </div>
      )}

      {/* ── 최우선 긴급 조치 권고 구역 ── */}
      {data && (data.top_recall_districts.length > 0 || data.top_deploy_districts.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20, marginBottom: 28 }}>
          {/* 회수 집중 구역 */}
          <div style={{ background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(56,189,248,0.2)', borderRadius: 16, padding: '20px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <span style={{ fontSize: 16 }}>🚚</span>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#F0F6FF', margin: 0 }}>
                따릉이 최우선 유휴 회수 구역 (Top 5)
              </h3>
            </div>
            {data.top_recall_districts.length === 0 ? (
              <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', margin: 0 }}>현재 기상 조건에서는 회수 대상 구역이 없습니다.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.top_recall_districts.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(56,189,248,0.2)', color: '#38BDF8', fontSize: 11, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {idx + 1}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: '#F0F6FF' }}>{item.district}</span>
                      <span style={{ fontSize: 11, color: '#EF4444', fontWeight: 600 }}>{item.delta_pct}% 급감</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: '#38BDF8' }}>
                      약 {item.qty}대 회수
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 배치 집중 구역 */}
          <div style={{ background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 16, padding: '20px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <span style={{ fontSize: 16 }}>📦</span>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#F0F6FF', margin: 0 }}>
                따릉이 최우선 긴급 배치 구역 (Top 5)
              </h3>
            </div>
            {data.top_deploy_districts.length === 0 ? (
              <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', margin: 0 }}>현재 기상 조건에서는 긴급 추가 배치 구역이 없습니다.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.top_deploy_districts.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(245,158,11,0.2)', color: '#F59E0B', fontSize: 11, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {idx + 1}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: '#F0F6FF' }}>{item.district}</span>
                      <span style={{ fontSize: 11, color: '#10B981', fontWeight: 600 }}>+{item.delta_pct}% 급증</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: '#F59E0B' }}>
                      약 {item.qty}대 공급
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── 25개 자치구 재배치 세부 현황 테이블 ── */}
      <div style={{ background: 'rgba(15,23,42,0.85)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 14 }}>
          <div>
            <h3 style={{ fontSize: 17, fontWeight: 800, color: '#F0F6FF', margin: 0 }}>
              서울시 25개 자치구 수급 분석 및 재배치 가이드
            </h3>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>
              기상 변화(강수/기온)에 따른 교통수단별 수요 변동률과 추천 재배치 수량입니다.
            </span>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {/* 검색창 */}
            <input
              type="text"
              placeholder="자치구 검색 (예: 강남구)"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              style={{
                padding: '8px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
                color: '#F0F6FF', fontSize: 12, outline: 'none', width: 160
              }}
            />

            {/* 필터 버튼들 */}
            <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.04)', padding: 3, borderRadius: 8 }}>
              {(['ALL', 'SURPLUS', 'DEFICIT', 'STABLE'] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setFilterStatus(st)}
                  style={{
                    padding: '6px 12px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                    background: filterStatus === st ? 'rgba(56,189,248,0.2)' : 'transparent',
                    border: 'none',
                    color: filterStatus === st ? '#38BDF8' : 'rgba(255,255,255,0.4)',
                    cursor: 'pointer'
                  }}
                >
                  {st === 'ALL' && '전체'}
                  {st === 'SURPLUS' && '🔴 회수권고'}
                  {st === 'DEFICIT' && '🟡 공급필요'}
                  {st === 'STABLE' && '⚪ 안정'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 테이블 */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.5)', fontSize: 11, fontWeight: 700 }}>
                <th style={{ padding: '14px 20px' }}>자치구</th>
                <th style={{ padding: '14px 16px' }}>따릉이 예상 수요</th>
                <th style={{ padding: '14px 16px' }}>수요 변동률</th>
                <th style={{ padding: '14px 16px' }}>수급 상태</th>
                <th style={{ padding: '14px 16px' }}>권장 조정 수량</th>
                <th style={{ padding: '14px 16px' }}>시내버스 배차</th>
                <th style={{ padding: '14px 20px' }}>운영 가이드 및 조치 사항</th>
              </tr>
            </thead>
            <tbody>
              {filteredList.map((item) => (
                <tr key={item.district} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.15s' }}>
                  <td style={{ padding: '14px 20px', fontWeight: 700, color: '#F0F6FF' }}>
                    {item.district}
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', fontWeight: 400 }}>
                      거치대 {item.infra.bike_racks}개소 · 정류소 {item.infra.bus_stops}개
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#E2E8F0', fontFamily: 'JetBrains Mono' }}>
                    {item.bike_demand}대 <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>(기준: {item.bike_baseline})</span>
                  </td>
                  <td style={{ padding: '14px 16px', fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
                    <span style={{ color: item.bike_delta_pct > 0 ? '#10B981' : item.bike_delta_pct < 0 ? '#EF4444' : '#94A3B8' }}>
                      {item.bike_delta_pct > 0 ? `+${item.bike_delta_pct}%` : `${item.bike_delta_pct}%`}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    {item.bike_status === 'SURPLUS' && (
                      <span style={{ display: 'inline-block', padding: '3px 8px', borderRadius: 4, background: 'rgba(239,68,68,0.15)', color: '#F87171', fontSize: 11, fontWeight: 700 }}>
                        과잉 (회수)
                      </span>
                    )}
                    {item.bike_status === 'DEFICIT' && (
                      <span style={{ display: 'inline-block', padding: '3px 8px', borderRadius: 4, background: 'rgba(245,158,11,0.15)', color: '#FBBF24', fontSize: 11, fontWeight: 700 }}>
                        부족 (공급)
                      </span>
                    )}
                    {item.bike_status === 'STABLE' && (
                      <span style={{ display: 'inline-block', padding: '3px 8px', borderRadius: 4, background: 'rgba(148,163,184,0.1)', color: '#94A3B8', fontSize: 11, fontWeight: 600 }}>
                        적정 유지
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px', fontWeight: 800, color: item.bike_rebalance_qty > 0 ? '#38BDF8' : '#64748B' }}>
                    {item.bike_rebalance_qty > 0 ? (
                      item.bike_action === 'RECALL' ? `약 ${item.bike_rebalance_qty}대 회수` : `약 ${item.bike_rebalance_qty}대 배치`
                    ) : (
                      '조정 불필요'
                    )}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    {item.bus_recommended_trips > 0 ? (
                      <span style={{ color: '#10B981', fontWeight: 700 }}>+{item.bus_recommended_trips}회 증차 권고</span>
                    ) : (
                      <span style={{ color: 'rgba(255,255,255,0.4)' }}>정상 배차</span>
                    )}
                  </td>
                  <td style={{ padding: '14px 20px', color: 'rgba(255,255,255,0.7)', fontSize: 12, lineHeight: 1.4 }}>
                    {item.actionable_guidance}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default EnterpriseView;

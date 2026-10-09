import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export default function LearningTrend({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 12, right: 5, left: -24, bottom: 0 }}>
        <defs>
          <linearGradient id="activeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#25846c" stopOpacity={0.16} />
            <stop offset="100%" stopColor="#25846c" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="#e9e8e2" strokeDasharray="3 4" />
        <XAxis dataKey="week" axisLine={false} tickLine={false} tick={{ fill: '#8a8b82', fontSize: 10 }} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#8a8b82', fontSize: 10 }} allowDecimals={false} />
        <Tooltip contentStyle={{ border: '1px solid #e7e5dc', borderRadius: 5, fontSize: 12 }} />
        <Area type="monotone" dataKey="active" stroke="#25846c" strokeWidth={2} fill="url(#activeFill)" />
        <Area type="monotone" dataKey="shipped" stroke="#d99049" strokeWidth={2} fill="transparent" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

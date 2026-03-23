<template>
  <div>
    <div class="text-subtitle2 q-mb-sm">Tasks completed per week (last 8 weeks)</div>
    <div v-if="hasData" style="position: relative; height: 220px;">
      <Line :data="chartData" :options="chartOptions" />
    </div>
    <div v-else class="text-caption text-grey-6">Not enough data yet.</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const props = defineProps<{
  data: { week: string; count: number }[];
}>();

const hasData = computed(() => props.data && props.data.length > 0);

const chartData = computed(() => ({
  labels: props.data.map((d) => d.week),
  datasets: [
    {
      label: 'Completions',
      data: props.data.map((d) => d.count),
      fill: true,
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.12)',
      tension: 0.35,
      pointRadius: 4,
    },
  ],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { stepSize: 1 } },
  },
};
</script>

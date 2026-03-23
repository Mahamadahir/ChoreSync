<template>
  <div>
    <div class="text-subtitle2 q-mb-sm">Completions by category</div>
    <div v-if="hasData" style="position: relative; height: 220px;">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
    <div v-else class="text-caption text-grey-6">Not enough data yet.</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const props = defineProps<{
  data: { category: string; count: number }[];
}>();

const hasData = computed(() => props.data && props.data.length > 0);

const PALETTE = ['#1976d2', '#26a69a', '#f57c00', '#7b1fa2', '#388e3c', '#e53935', '#0288d1', '#fbc02d'];

const chartData = computed(() => ({
  labels: props.data.map((d) => d.category),
  datasets: [
    {
      label: 'Tasks',
      data: props.data.map((d) => d.count),
      backgroundColor: props.data.map((_, i) => PALETTE[i % PALETTE.length]),
      borderRadius: 4,
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

<template>
  <div>
    <div class="text-subtitle2 q-mb-sm">Tasks completed per member</div>
    <div v-if="hasData" style="position: relative; height: 240px;">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
    <div v-else class="text-caption text-grey-6">No data yet.</div>
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
  distribution: { username: string; total_tasks_completed: number; total_points: number }[];
}>();

const hasData = computed(() => props.distribution && props.distribution.length > 0);

const chartData = computed(() => ({
  labels: props.distribution.map((d) => d.username),
  datasets: [
    {
      label: 'Tasks completed',
      data: props.distribution.map((d) => d.total_tasks_completed),
      backgroundColor: 'rgba(25, 118, 210, 0.75)',
      borderRadius: 4,
    },
    {
      label: 'Points',
      data: props.distribution.map((d) => d.total_points),
      backgroundColor: 'rgba(245, 124, 0, 0.65)',
      borderRadius: 4,
    },
  ],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y' as const,
  plugins: {
    legend: { position: 'top' as const },
  },
  scales: {
    x: { beginAtZero: true, ticks: { stepSize: 1 } },
  },
};
</script>

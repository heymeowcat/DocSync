<template>
  <div class="min-h-screen bg-gray-100 p-6">
    <div class="max-w-4xl mx-auto bg-white shadow-md rounded-lg p-6 space-y-8">
      <h1 class="text-2xl font-bold mb-4 text-gray-800">
        Git Commit Difference Viewer
      </h1>
      <!-- File Selector for Project (with Git Repo) -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700"
          >Select a Project (Git Repo)</label
        >
        <input
          type="file"
          webkitdirectory
          directory
          @change="onFilePickerChange($event)"
          class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
        />
      </div>
      <!-- Branch Selection -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700"
          >Select a Branch</label
        >
        <select
          v-model="selectedBranch"
          @change="onBranchChange"
          class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
        >
          <option value="">Select a branch</option>
          <option v-for="branch in branches" :key="branch">{{ branch }}</option>
        </select>
      </div>
      <!-- Commit Selection -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700"
          >Select a Commit Hash From</label
        >
        <input
          v-model="commitHashFrom"
          type="text"
          class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
        />
        <label class="block text-sm font-medium text-gray-700 mt-4"
          >Select a Commit Hash To</label
        >
        <input
          v-model="commitHashTo"
          type="text"
          class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
        />
      </div>
      <!-- Compare Button -->
      <button
        @click="compareCommits"
        class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
      >
        Compare Commits
      </button>
      <!-- Comparison UI -->
      <div v-if="comparisonResult" class="mt-8">
        <h2 class="text-lg font-semibold mb-2">Comparison Result</h2>
        <VueDiff :diff="comparisonResult.diff" />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from "vue";
import axios from "axios";
import VueDiff from "vue-diff"; // Import VueDiff component

export default defineComponent({
  components: {
    VueDiff, // Register VueDiff component
  },
  setup() {
    const selectedBranch = ref("");
    const branches = ref([]);
    const commits = ref([]);
    const commitHashFrom = ref("");
    const commitHashTo = ref("");
    const comparisonResult = ref({ diff: "" });
    const repoPath = ref(""); // Store the repo path

    const onFilePickerChange = async (event: Event) => {
      const target = event.target as HTMLInputElement;
      if (!target.files || !target.files[0]) return;

      repoPath.value = target.files[0].path;
      try {
        const response = await axios.post(
          "http://localhost:5000/get-branches",
          { filePath: repoPath.value },
          { headers: { "Content-Type": "application/json" } }
        );
        branches.value = response.data.branches;
      } catch (error: any) {
        // More detailed error handling
        if (error.response) {
          // The request was made and the server responded with a status code
          console.error("Server Error:", error.response.data);
          console.error("Status Code:", error.response.status);
        } else if (error.request) {
          // The request was made but no response was received
          console.error("No response received:", error.request);
        } else {
          // Something happened in setting up the request
          console.error("Error setting up request:", error.message);
        }
      }
    };

    const onBranchChange = async () => {
      if (!selectedBranch.value) return;
      try {
        const response = await axios.post(
          "http://localhost:5000/get-commits",
          {
            branchName: selectedBranch.value,
            repoPath: repoPath.value, // Send the repo path
          },
          {
            headers: {
              "Content-Type": "application/json",
            },
          }
        );
        commits.value = response.data.commits;
        commitHashFrom.value = commits.value[0].hash; // Pre-fill first commit hash
      } catch (error) {
        console.error("Error fetching commits:", error);
      }
    };

    const compareCommits = async () => {
      if (!commitHashFrom.value || !commitHashTo.value) return;
      try {
        const response = await axios.post(
          "http://localhost:5000/compare-commits",
          {
            fromHash: commitHashFrom.value,
            toHash: commitHashTo.value,
            repoPath: repoPath.value, // Send the repo path
          },
          {
            headers: {
              "Content-Type": "application/json",
            },
          }
        );
        comparisonResult.value = response.data;
      } catch (error) {
        console.error("Error comparing commits:", error);
      }
    };

    return {
      selectedBranch,
      branches,
      commits,
      commitHashFrom,
      commitHashTo,
      onFilePickerChange,
      onBranchChange,
      compareCommits,
      comparisonResult,
    };
  },
});
</script>

<style>
/* Add your styles here */
</style>

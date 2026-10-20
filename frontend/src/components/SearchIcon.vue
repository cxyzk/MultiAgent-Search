<template>
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
    <!-- 地球仪：外圆 + 纵向经线 + 横向赤道（DeepSeek 智能搜索造型）
         r=6.8 让外圆落在 1.2~14.8，与深度思考的轨道视觉重量一致 -->
    <circle
        cx="8" cy="8" r="6.8"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round">
    </circle>
    <ellipse
        cx="8" cy="8" rx="3.05" ry="6.8"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round">
    </ellipse>
    <path
        d="M1.2 8H14.8"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round">
    </path>
  </svg>
</template>

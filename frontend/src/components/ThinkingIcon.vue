<template>
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
    <!-- 原子轨道：两条 ±45° 交叉椭圆 + 中心原子核（DeepSeek 深度思考造型）
         rx=8.83 / ry=3.8 是算出来的：旋转 45° 后包围盒半宽正好 6.8，
         即 x 落在 1.2~14.8，撑满画布又不会被裁切；长短比 2.32 接近官方观感 -->
    <ellipse
        cx="8" cy="8" rx="8.83" ry="3.8"
        transform="rotate(45 8 8)"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round">
    </ellipse>
    <ellipse
        cx="8" cy="8" rx="8.83" ry="3.8"
        transform="rotate(-45 8 8)"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round">
    </ellipse>
    <circle cx="8" cy="8" r="1.2" fill="currentColor"></circle>
  </svg>
</template>

<template>
  <div class="typing" aria-label="正在生成回复">
    <span />
    <span />
    <span />
  </div>
</template>

<style scoped>
.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 26px;
}

.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.4s infinite ease-in-out both;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: scale(0.85);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>

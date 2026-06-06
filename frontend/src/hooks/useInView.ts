import { useEffect, useState, type RefObject } from "react";

// useInView 通过 IntersectionObserver 监听元素是否进入视口
// 一旦进入视口即返回 true，并停止后续观察以保留懒加载语义
export function useInView<T extends Element>(
  ref: RefObject<T | null>,
  options?: IntersectionObserverInit,
): boolean {
  const [inView, setInView] = useState(false);

  useEffect(() => {
    // 1. 浏览器不支持 IntersectionObserver 时直接返回可见，避免内容永久缺失
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const target = ref.current;
    if (!target) {
      return;
    }
    // 2. 进入视口后置位并解除观察，实现一次性懒加载
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
          break;
        }
      }
    }, options);
    observer.observe(target);
    return () => observer.disconnect();
  }, [ref, options]);

  return inView;
}

import { clsx, type ClassValue } from "clsx";

/** 简易 className 合并（对齐 Multica cn 用法） */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

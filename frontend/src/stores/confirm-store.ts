import { create } from "zustand";

export type ConfirmOptions = {
  title?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
};

type ConfirmState = {
  open: boolean;
  message: string;
  title: string;
  confirmText: string;
  cancelText: string;
  danger: boolean;
  resolve: ((ok: boolean) => void) | null;
  ask: (message: string, options?: ConfirmOptions) => Promise<boolean>;
  finish: (ok: boolean) => void;
};

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  open: false,
  message: "",
  title: "确认操作",
  confirmText: "确认",
  cancelText: "取消",
  danger: false,
  resolve: null,
  ask: (message, options = {}) =>
    new Promise<boolean>((resolve) => {
      set({
        open: true,
        message,
        title: options.title || "确认操作",
        confirmText: options.confirmText || "确认",
        cancelText: options.cancelText || "取消",
        danger: !!options.danger,
        resolve,
      });
    }),
  finish: (ok) => {
    const { resolve, open } = get();
    if (!open || !resolve) return;
    set({ open: false, resolve: null });
    resolve(ok);
  },
}));

export function confirmAction(
  message: string,
  options?: ConfirmOptions,
): Promise<boolean> {
  return useConfirmStore.getState().ask(message, options);
}

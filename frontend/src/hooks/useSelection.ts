/**
 * useSelection - 选区检测 Hook
 * 监听 TipTap 编辑器选区变化，提供选区位置信息
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { Editor } from '@tiptap/react';

export interface SelectionInfo {
  text: string;
  from: number;
  to: number;
  empty: boolean;
}

export interface Position {
  top: number;
  left: number;
  bottom: number;
}

interface UseSelectionOptions {
  debounceMs?: number;
  minLength?: number;
}

interface UseSelectionReturn {
  selection: SelectionInfo | null;
  position: Position | null;
  isVisible: boolean;
}

export function useSelection(
  editor: Editor | null,
  options: UseSelectionOptions = {}
): UseSelectionReturn {
  const { debounceMs = 500, minLength = 1 } = options;

  const [selection, setSelection] = useState<SelectionInfo | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  const updateSelection = useCallback(() => {
    if (!editor) {
      setSelection(null);
      setPosition(null);
      setIsVisible(false);
      return;
    }

    const { from, to, empty } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to);

    // 如果选区为空或文本长度不足，隐藏菜单
    if (empty || text.length < minLength) {
      setSelection(null);
      setPosition(null);
      setIsVisible(false);
      return;
    }

    // 获取选区的 DOM 坐标
    try {
      const { view } = editor;
      const start = view.coordsAtPos(from);
      const end = view.coordsAtPos(to);

      // 检查选区是否超出视口边界
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;

      if (
        start.top < 0 ||
        end.bottom > viewportHeight ||
        start.left < 0 ||
        end.right > viewportWidth
      ) {
        // 选区超出边界，隐藏菜单
        setSelection(null);
        setPosition(null);
        setIsVisible(false);
        return;
      }

      setSelection({ text, from, to, empty });
      setPosition({
        top: start.top,
        left: (start.left + end.right) / 2,
        bottom: end.bottom,
      });
      setIsVisible(true);
    } catch (e) {
      // 坐标获取失败，隐藏菜单
      setSelection(null);
      setPosition(null);
      setIsVisible(false);
    }
  }, [editor, minLength]);

  // 防抖处理
  const debouncedUpdateSelection = useCallback(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      updateSelection();
    }, debounceMs);
  }, [updateSelection, debounceMs]);

  // 监听编辑器选区变化
  useEffect(() => {
    if (!editor) {
      return;
    }

    // 初始化
    updateSelection();

    // 监听选区变化
    editor.on('selectionUpdate', debouncedUpdateSelection);
    editor.on('focus', debouncedUpdateSelection);
    editor.on('blur', () => {
      // 延迟隐藏，给菜单点击留时间
      setTimeout(() => {
        setIsVisible(false);
        setSelection(null);
        setPosition(null);
      }, 200);
    });

    return () => {
      editor.off('selectionUpdate', debouncedUpdateSelection);
      editor.off('focus', debouncedUpdateSelection);
      editor.off('blur');

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [editor, debouncedUpdateSelection, updateSelection]);

  return { selection, position, isVisible };
}

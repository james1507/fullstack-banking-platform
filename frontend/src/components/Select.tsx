import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentPropsWithRef,
  type CSSProperties,
  type KeyboardEvent,
} from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';

type Option = { value: string; label: string; description?: string };
type Props = Omit<ComponentPropsWithRef<'button'>, 'value' | 'onChange' | 'children'> & {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
};

export function Select({
  value,
  options,
  onChange,
  disabled,
  ref,
  className = '',
  ...props
}: Props) {
  const uid = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const search = useRef({ text: '', time: 0 });
  const [position, setPosition] = useState<CSSProperties | null>(null);
  const [active, setActive] = useState(0);
  const selected = options.findIndex((option) => option.value === value);
  const open = position !== null && !disabled;
  const listId = `${uid}-options`;
  const measure = useCallback((): CSSProperties => {
    const rect = trigger.current!.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 16;
    const above = rect.top - 16;
    const flip = below < Math.min(300, options.length * 64 + 12) && above > below;
    const width = Math.min(Math.max(rect.width, 240), window.innerWidth - 16);
    return {
      width,
      left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
      top: flip ? undefined : rect.bottom + 8,
      bottom: flip ? window.innerHeight - rect.top + 8 : undefined,
      maxHeight: Math.max(0, Math.min(320, flip ? above : below)),
    };
  }, [options.length]);

  useEffect(() => {
    if (!open) return;
    const reposition = () => setPosition(measure());
    const outside = (event: Event) => {
      if (
        !trigger.current?.contains(event.target as Node) &&
        !menu.current?.contains(event.target as Node)
      )
        setPosition(null);
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
    };
  }, [open, measure]);
  useEffect(() => {
    if (disabled) setPosition(null);
  }, [disabled]);
  useLayoutEffect(() => {
    if (open)
      menu.current?.querySelector('[data-active="true"]')?.scrollIntoView?.({ block: 'nearest' });
  }, [active, open]);

  function show(index = Math.max(selected, 0)) {
    if (disabled || !options.length) return;
    setActive(index);
    search.current.text = '';
    setPosition(measure());
  }
  function choose(index: number) {
    if (!options[index]) return;
    onChange(options[index].value);
    setPosition(null);
    trigger.current?.focus({ preventScroll: true });
  }
  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Tab' || event.key === 'Escape') {
      if (open && event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
      }
      setPosition(null);
      return;
    }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? options.length - 1
            : Math.max(
                0,
                Math.min(options.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1)),
              );
      if (open) setActive(next);
      else show(event.key === 'Home' || event.key === 'End' ? next : Math.max(selected, 0));
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (open) choose(active);
      else show();
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      const now = Date.now();
      const text =
        (now - search.current.time < 600 ? search.current.text : '') + event.key.toLowerCase();
      search.current = { text, time: now };
      const prefix = [...text].every((char) => char === text[0]) ? text[0] : text;
      const continuing = text.length > 1 && prefix === text;
      const start = open ? active - Number(continuing) : selected;
      const index = options.findIndex((_, offset) =>
        options[(start + 1 + offset) % options.length].label.toLowerCase().startsWith(prefix),
      );
      if (index >= 0) {
        const match = (start + 1 + index) % options.length;
        if (open) setActive(match);
        else {
          show(match);
          search.current = { text, time: now };
        }
      }
    }
  }
  return (
    <>
      <button
        {...props}
        ref={(node) => {
          trigger.current = node;
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? `${uid}-${active}` : undefined}
        disabled={disabled || !options.length}
        className={`select-trigger ${className}`}
        data-open={open}
        onClick={() => (open ? setPosition(null) : show())}
        onKeyDown={keyDown}
      >
        <span className="select-value">{options[selected]?.label || 'Choose an account'}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {open &&
        createPortal(
          <div
            id={listId}
            ref={menu}
            role="listbox"
            aria-label={props['aria-label'] || 'Account options'}
            className="select-menu"
            style={position!}
          >
            {options.map((option, index) => (
              <div
                id={`${uid}-${index}`}
                key={option.value}
                role="option"
                aria-selected={index === selected}
                data-active={index === active}
                className="select-option"
                onPointerMove={() => setActive(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(index)}
              >
                <span className="select-option-content">
                  <span className="select-option-label">{option.label}</span>
                  {option.description && (
                    <span className="select-option-description">{option.description}</span>
                  )}
                </span>
                <Check size={16} className="select-check" aria-hidden="true" />
              </div>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}

import { useId, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { getCountryAutocompleteOptions } from "@/lib/country";

interface CountryAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  maxLength?: number;
  id?: string;
}

export function CountryAutocomplete({
  value,
  onChange,
  placeholder,
  className,
  maxLength = 32,
  id,
}: CountryAutocompleteProps) {
  const { i18n } = useTranslation();
  const autoId = useId();
  const listId = `${id ?? autoId}-countries`;
  const options = useMemo(
    () => getCountryAutocompleteOptions(i18n.language),
    [i18n.language],
  );

  return (
    <>
      <input
        id={id}
        type="text"
        list={listId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={className}
        maxLength={maxLength}
      />
      <datalist id={listId}>
        {options.map((option) => (
          <option key={option.code} value={option.name} label={option.code} />
        ))}
      </datalist>
    </>
  );
}


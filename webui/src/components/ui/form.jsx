import React from 'react';
import { FormProvider, useFormContext, Controller } from 'react-hook-form';
import { cn } from '../../lib/utils';

export function Form({ children, ...props }) {
  return <form {...props}>{children}</form>;
}

export function RHFProvider({ methods, children, onSubmit, className }) {
  return (
    <FormProvider {...methods}>
      <form onSubmit={methods.handleSubmit(onSubmit)} className={className}>
        {children}
      </form>
    </FormProvider>
  );
}

export function FormField({ name, render }) {
  const { control } = useFormContext();
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState, formState }) => render({ field, fieldState, formState })}
    />
  );
}

export function FormItem({ className, ...props }) {
  return <div className={cn('space-y-1', className)} {...props} />;
}

export function FormLabel({ className, ...props }) {
  return <label className={cn('text-sm font-medium', className)} {...props} />;
}

export function FormControl({ className, ...props }) {
  return <div className={cn('', className)} {...props} />;
}

export function FormDescription({ className, ...props }) {
  return <p className={cn('text-xs text-gray-500', className)} {...props} />;
}

export function FormMessage({ className, children }) {
  if (!children) return null;
  return <p className={cn('text-xs text-red-600', className)}>{children}</p>;
} 
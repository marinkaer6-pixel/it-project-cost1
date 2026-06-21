from decimal import Decimal
from typing import List

# УБРАЛИ: from Back.models import ProjectResourceDB

def calculate_employee_cost(days: int, monthly_salary: Decimal, tax_rate: Decimal) -> Decimal:
    """Облегченный расчет сотрудника"""
    if days == 0:
        return Decimal(0)
    daily_cost_with_tax = (monthly_salary + (monthly_salary * tax_rate / 100)) / Decimal(22)
    return days * daily_cost_with_tax

def calculate_contractor_cost(units: int, price_per_unit: Decimal, tax_rate: Decimal) -> Decimal:
    """Расчет исполнителя (ГПХ/НПД)"""
    base_cost = units * price_per_unit
    tax_cost = base_cost * tax_rate / 100
    return base_cost + tax_cost

def calculate_equipment_cost(units: int, price_per_unit: Decimal) -> Decimal:
    """Расчет оборудования"""
    return units * price_per_unit

def calculate_service_total_cost(cost_price: Decimal, margin_percent: Decimal) -> Decimal:
    """Итоговая стоимость услуги с маржинальностью: i = s + (s * m / 100)"""
    return cost_price + (cost_price * margin_percent / 100)

def calculate_project_total_cost(sp: Decimal, tax_rate: Decimal) -> Decimal:
    """Итоговая стоимость проекта с налогом: isp = sp + (sp * ns / 100)"""
    return sp + (sp * tax_rate / 100)

def calculate_pure_profit(resources) -> Decimal:
    """Чистая прибыль: p = Σ(i - s) по каждой услуге"""
    total_profit = Decimal(0)
    for res in resources:
        diff = res.total_cost - res.cost_price
        total_profit += diff
    return total_profit

def recalculate_project(project, resources) -> dict:
    """
    Пересчет ВСЕГО проекта после добавления/удаления ресурса.
    Возвращает словарь с новыми расчетами.
    """
    total_cost_price = Decimal(0)
    total_cost_with_margin = Decimal(0)
    
    for res in resources:
        total_cost_price += res.cost_price
        total_cost_with_margin += res.total_cost
    
    project.cost_price = total_cost_price
    project.total_cost_nma = total_cost_price
    project.total_cost_cp = total_cost_with_margin
    project.total_cost_project = calculate_project_total_cost(total_cost_with_margin, project.tax_rate)
    project.pure_profit = calculate_pure_profit(resources)
    
    return {
        "cost_price": str(project.cost_price),
        "total_cost_nma": str(project.total_cost_nma),
        "total_cost_cp": str(project.total_cost_cp),
        "total_cost_project": str(project.total_cost_project),
        "pure_profit": str(project.pure_profit)
    }
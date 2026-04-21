<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('tenants', function (Blueprint $table) {
            $table->id();

            // Basic Info
            $table->string('company_name');
            $table->string('slug')->unique(); // for subdomain: company.app.com

            // Contact Info
            $table->string('email')->nullable();
            $table->string('phone')->nullable();
            $table->string('address')->nullable();

            // Business Info
            $table->string('industry')->nullable();
            $table->integer('employee_size')->nullable();

            // Plan / Billing
            $table->foreignId('plan_id')->index();
            $table->integer('max_users')->default(10);
            $table->integer('max_calls_per_day')->default(1000);

            // Usage tracking (VERY IMPORTANT)
            $table->integer('current_users')->default(0);
            $table->integer('current_calls_today')->default(0);

            // Status
            $table->enum('status', ['active','suspended','trial'])->default('trial');

            // Metadata
            $table->json('settings')->nullable();

            $table->timestamps();

            $table->index(['status','plan_id']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('tenants');
    }
};
